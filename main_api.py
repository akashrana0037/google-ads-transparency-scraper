from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import asyncio
import sys
import json
import os
import uuid
import shutil
import glob
from datetime import datetime, timezone, timedelta
from typing import Optional, List
import logging
import socket

# -- Windows asyncio fix ------------------------------------------------------
# Playwright requires ProactorEventLoop on Windows to launch subprocesses.
# The default SelectorEventLoop raises NotImplementedError on subprocess calls.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Import core elements from scraper.py
# (We will wrap them in a callable function in scraper.py)
import scraper 
import traceback
from contextlib import asynccontextmanager

# Global memory to track active tasks
ACTIVE_TASKS = {}
ACTIVE_ASYNC_TASKS = {} # Map task_id -> asyncio.Task object
OUTPUT_DIR = os.path.abspath("./output")

# --- CONCURRENCY GUARD ---
# Limit the number of HEAVY scraping missions running at once to save CPU/RAM.
# Any missions beyond this limit will stay in 'queued' until a slot opens.
MAX_CONCURRENT_MISSIONS = 3
CONCURRENCY_SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_MISSIONS)

OUTPUT_TTL_MINUTES = 120  # Auto-delete output folders after 2 hours (was 15min)

def purge_old_output_dirs():
    """Delete task output folders older than OUTPUT_TTL_MINUTES."""
    if not os.path.exists(OUTPUT_DIR):
        return
    cutoff = datetime.now() - timedelta(minutes=OUTPUT_TTL_MINUTES)
    for entry in os.scandir(OUTPUT_DIR):
        if not entry.is_dir():
            continue
        try:
            mtime = datetime.fromtimestamp(entry.stat().st_mtime)
            if mtime < cutoff:
                # CRITICAL: Do NOT delete if the task is currently active/running in memory
                if entry.name in ACTIVE_TASKS:
                    logging.debug(f"[Cleanup] Skipping active mission folder: {entry.name}")
                    continue
                
                shutil.rmtree(entry.path)
                logging.info(f"[Cleanup] Purged expired task folder: {entry.name}")
                # Also evict from in-memory task registry
                if entry.name in ACTIVE_TASKS:
                    del ACTIVE_TASKS[entry.name]
        except Exception as e:
            # Silence WinError 32 (file lock) which is extremely common on Windows during scans
            if "[WinError 32]" not in str(e):
                logging.warning(f"[Cleanup] Could not delete {entry.name}: {e}")

async def background_cleanup_loop():
    """Runs every 60s to purge output folders older than OUTPUT_TTL_MINUTES."""
    while True:
        await asyncio.sleep(60)  # Check every minute
        purge_old_output_dirs()

@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Zombie Task Recovery
    for task_id in os.listdir(OUTPUT_DIR):
        checkpoint_file = os.path.join(OUTPUT_DIR, task_id, "mission_state.json")
        if os.path.exists(checkpoint_file):
            try:
                with open(checkpoint_file, 'r') as f:
                    state = json.load(f)
                run_meta = state.get("run_meta", {})
                if run_meta.get("status") in ["running", "scraping_serp", "harvesting_contacts", "verifying_ads"]:
                    run_meta["status"] = "crashed"
                    scraper.export_excel(state, os.path.join(OUTPUT_DIR, task_id), partial=True)
                    with open(checkpoint_file, 'w') as f:
                        json.dump(state, f, indent=2)
                    logging.info(f" [Recovery] Recovered dead task {task_id}.")
            except Exception as e:
                logging.error(f" [Recovery] Failed to recover {task_id}: {e}")
                
    purge_old_output_dirs()  # Immediate cleanup on startup
    # Start the background periodic cleanup
    cleanup_task = asyncio.create_task(background_cleanup_loop())
    yield
    cleanup_task.cancel()  # Graceful shutdown

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

app = FastAPI(title="Vector-Eye Engine API", lifespan=lifespan)

# Enable CORS for the React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
)
class ScrapeTask:
    def __init__(self, task_id, keywords, location, pages):
        self.task_id = task_id
        self.keywords = keywords
        self.location = location
        self.pages = pages
        self.status = "queued"
        self.progress = 0
        self.results_count = 0
        self.atc_count = 0
        self.start_time = None
        self.logs = ["Mission Initialized. Protocol: Elite v3.5"]
        self.aborted = False
        self.checkpoint_file = None
        self.csv_file = None
        self.error = None
        self.active_variant = "Initializing..."
        self.discovered_keywords = []
        self.approval_event = asyncio.Event()

    def log(self, message):
        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
        self.logs.append(f"[{timestamp}] {message}")
        # Keep last 50 logs only for performance
        if len(self.logs) > 50:
            self.logs.pop(0)

def rehydrate_task(task_id: str):
    """Attempt to recover task metadata from disk if missing in memory."""
    if task_id in ACTIVE_TASKS:
        return ACTIVE_TASKS[task_id]
    
    task_dir = os.path.join(OUTPUT_DIR, task_id)
    checkpoint_file = os.path.join(task_dir, "mission_state.json")
    
    if os.path.exists(checkpoint_file):
        try:
            with open(checkpoint_file, 'r') as f:
                state = json.load(f)
                run_meta = state.get("run_meta", {})
                
                # Reconstruct ScrapeTask
                task = ScrapeTask(
                    task_id=task_id,
                    keywords=run_meta.get("keywords", "rehydrated"),
                    location=run_meta.get("location", ""),
                    pages=run_meta.get("max_pages", 1)
                )
                
                # Zombie Prevention: If it was left 'running' on disk but isn't in ACTIVE_TASKS,
                # it means the server crashed/stopped mid-mission. Mark as aborted.
                saved_status = run_meta.get("status", "completed")
                task.status = "aborted" if saved_status in ["running", "starting"] else saved_status
                
                task.start_time = run_meta.get("started_at")
                task.checkpoint_file = checkpoint_file
                task.active_variant = run_meta.get("active_variant", "Restored Session")
                
                # Locate CSV results if present
                for file in os.listdir(task_dir):
                    if file.endswith(".csv"):
                        task.csv_file = os.path.abspath(os.path.join(task_dir, file))
                        break
                
                # Sync counts
                competitors = state.get("competitors_found", [])
                task.results_count = len(competitors)
                task.atc_count = len([c for c in competitors if c.get("result_type") == "Ad"])
                
                task.log(f"Session Re-hydrated from disk. Status: {task.status.upper()}")
                ACTIVE_TASKS[task_id] = task
                return task
        except Exception as e:
            logging.error(f"Re-hydration failed for {task_id}: {str(e)}")
    
    return None

async def run_scraper_task(task: ScrapeTask):
    """
    Orchestrates the background execution of the scraper.
    Utilizes the CONCURRENCY_SEMAPHORE to ensure the host doesn't crash from too many parallel missions.
    """
    task_id = task.task_id
    try:
        async with CONCURRENCY_SEMAPHORE:
            # Re-check status in case it was cancelled while in queue
            if task.status == "aborted":
                return
            
            task.status = "starting"
            task.start_time = datetime.now(timezone.utc).isoformat()
            task.log(f"Mission Initiated. Concurrency Slot Acquired ({MAX_CONCURRENT_MISSIONS} slots total).")
            
            output_dir = os.path.join(OUTPUT_DIR, task.task_id)
            os.makedirs(output_dir, exist_ok=True)
            task.checkpoint_file = os.path.join(output_dir, "mission_state.json")
            
            # We'll call the refactored 'run_autonomous_scrape' (to be added to scraper.py)
            result = await scraper.run_autonomous_scrape(
                keywords=task.keywords,
                location=task.location,
                pages=task.pages,
                checkpoint_file=task.checkpoint_file,
                output_dir=output_dir,
                task_ref=task, # Pass reference to update progress/logs
                headless=getattr(task, 'headless', True)
            )
            
            if not task.aborted:
                task.status = "completed"
                task.csv_file = result["csv_file"]
                task.results_count = len(result.get("results", []))
                task.log("Mission Completed Successfully.")
            
    except asyncio.CancelledError:
        task.status = "aborted"
        task.log("Mission ABORTED by user command.")
        raise
    except Exception as e:
        task.status = "failed"
        # Capture full traceback for debugging in the UI
        task.error = f"{str(e)}\n\n{traceback.format_exc()}"
        task.log(f"Mission FAILED: {str(e)}")
        logging.error(f"Task {task.task_id} failed: {task.error}")

def cleanup_task_resources(task):
    # This would involve closing browsers if we had direct access to them,
    # but since they're in run_autonomous_scrape, we'll rely on it checking the flag.
    pass

@app.post("/api/scrape")
async def start_scrape(keywords: str, location: str = "India", pages: int = 1, headless: bool = True):
    task_id = str(uuid.uuid4())[:8]
    task = ScrapeTask(task_id, keywords, location, pages)
    task.headless = headless
    
    # Register in memory for live status polling
    ACTIVE_TASKS[task_id] = task
    
    # Instead of FastAPI's BackgroundTasks, we use direct asyncio.create_task
    # to allow for immediate cancellation later.
    async_task = asyncio.create_task(run_scraper_task(task))
    ACTIVE_ASYNC_TASKS[task_id] = async_task
    
    return {"task_id": task_id, "status": "queued"}

@app.get("/api/status/{task_id}")
async def get_status(task_id: str):
    task = rehydrate_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    output_dir = os.path.join(OUTPUT_DIR, task_id)
    
    # Try to extract the most recent variant from the mission checkpoint
    active_variant = task.active_variant
    if task.checkpoint_file and os.path.exists(task.checkpoint_file):
        try:
            with open(task.checkpoint_file, 'r') as f:
                state = json.load(f)
                active_variant = state.get("run_meta", {}).get("active_variant", task.active_variant)
                # Sync results count from checkpoint for higher fidelity
                task.results_count = len(state.get("competitors_found", []))
                # Update ATC count
                task.atc_count = len([c for c in state.get("competitors_found", []) if c.get("result_type") == "Ad"])
        except:
            pass

    return {
        "status": task.status,
        "progress": task.progress,
        "results_count": task.results_count,
        "atc_count": task.atc_count,
        "active_variant": active_variant,
        "start_time": task.start_time,
        "logs": task.logs,
        "csv_available": task.csv_file is not None and os.path.exists(task.csv_file),
        "error": task.error,
        "discovered_keywords": task.discovered_keywords
    }

@app.post("/api/confirm/{task_id}")
async def confirm_keywords(task_id: str, keywords: List[str]):
    task = rehydrate_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task.discovered_keywords = keywords
    task.log(f"Sector List Approved: {len(keywords)} targets confirmed. Resuming engine...")
    task.approval_event.set()
    return {"status": "resuming"}

@app.post("/api/abort/{task_id}")
async def abort_scrape(task_id: str):
    task = rehydrate_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task.aborted = True
    task.status = "aborted"
    task.log("User issued abort command. Terminating engine...")
    
    # NEW: Immediate Async Cancellation
    if task_id in ACTIVE_ASYNC_TASKS:
        async_task = ACTIVE_ASYNC_TASKS[task_id]
        if not async_task.done():
            async_task.cancel()
            logging.info(f" [!] Task {task_id} manually cancelled by user.")
    
    return {"status": "aborting"}

@app.get("/api/download_excel/{task_id}")
async def download_excel(task_id: str):
    output_dir = os.path.join(OUTPUT_ROOT, task_id)
    files = glob.glob(os.path.join(output_dir, "*.xlsx"))
    if not files:
        raise HTTPException(status_code=404, detail="Excel file not found")
    
    # Return the latest xlsx file
    latest_file = max(files, key=os.path.getmtime)
    return FileResponse(latest_file, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', filename=os.path.basename(latest_file))

@app.get("/api/results/{task_id}")
async def get_results(task_id: str):
    task = rehydrate_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Mission ID not found.")
    
    if task.checkpoint_file and os.path.exists(task.checkpoint_file):
        try:
            with open(task.checkpoint_file, 'r') as f:
                state = json.load(f)
                competitors = state.get("competitors_found", [])
                contacts = state.get("contacts_harvested", {})
                
                # Merge contacts into competitors
                merged = []
                for c in competitors:
                    merged.append({
                        **c,
                        "contacts": contacts.get(c['domain'], {})
                    })
                return merged
        except:
            return []
    return []

@app.get("/api/download/{task_id}")
async def download_results(task_id: str):
    logging.info(f" [Download] Request for mission: {task_id}")
    task = rehydrate_task(task_id)
    
    if not task:
        logging.warning(f" [Download] MISSION NOT FOUND: {task_id}")
        raise HTTPException(status_code=404, detail="Mission ID not found")
        
    if not task.csv_file:
        logging.warning(f" [Download] CSV PATH NOT SET for mission: {task_id}")
        raise HTTPException(status_code=404, detail="File path not identified in mission state")
    
    file_path = os.path.abspath(task.csv_file)
    logging.info(f" [Download] Attempting to serve file: {file_path}")
    
    if os.path.exists(file_path):
        filename = os.path.basename(file_path)
        logging.info(f" [Download] SUCCESS: Serving {filename}")
        return FileResponse(
            path=file_path, 
            filename=filename, 
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    
    logging.error(f" [Download] FILE NOT FOUND ON DISK: {file_path}")
    raise HTTPException(status_code=404, detail="The report file does not exist or was already purged")

if __name__ == "__main__":
    import uvicorn
    local_ip = get_local_ip()
    print("\n" + "="*50)
    print(f"[*] VECTOR-EYE ENGINE ONLINE")
    print(f"   Local Access:   http://localhost:8000")
    print(f"   Network Access: http://{local_ip}:8000")
    print("="*50 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=8000, loop="asyncio")
