# ⚡ VYOM v2.0
### Autonomous Google Ads Sector Intelligence & Competitor Engine

**Vyom** (Sanskrit for *Sky* / *Space*) is a precision-engineered intelligence engine designed to map out entire commercial sectors by identifying active advertisers and harvesting high-value metadata directly from Google Search SERPs and the **Google Ads Transparency Center (ATC)**. 

Vyom is built for scale: it strictly filters for active ad-spend targets and optimizes performance by bypassing resource-heavy website crawling, preventing memory issues and uvicorn process crashes.

---

## 🚀 Key Features

### 1. 🧠 Alphabet Soup Sector Discovery
Provide a single sector (e.g., *"Luxury Real Estate"*), and Vyom autonomously discovers the **Top 20 transactional keywords** using:
* **Alphabet Expansion**: Appending `[a-z]` query modifiers.
* **Transactional Intent Scoring**: Prioritizing keywords with buying signals (*price, agency, best, quote*).
* **PAA mining**: Converting question-intent SERP queries into transactional targets.

### 2. 🔍 Double-Source SERP Extraction (Bypassed Local Pack)
To save system memory, the engine focuses purely on high-intent listings:
* **Paid Ads**: Playwright-native extraction catches dynamically rendered ads.
* **Organic Websites**: Extracts top organic listings.
* **Local Listings Bypassed**: Google Maps/Local pack results are excluded from extraction, keeping the scraper fast and clean.

### 3. 🛡️ Ads Transparency Center (ATC) Verification & Output Filtering
* **Direct Verification**: All extracted domains are queried directly against Google's Ads Transparency Center to check verified company names, advertiser IDs, and active ad counts.
* **Strict Output Filter**: Both final report files (CSV, Excel) and the dashboard's **Intelligence Grid** only show listings verified as active advertisers (ad count > 0), completely filtering out non-advertiser noise.

### 4. ⚡ Zero-Crawling Architecture (No Server Crashes)
* **Bypassed Contact Harvest**: Does not crawl individual competitor homepages or contact pages for emails/phones. Bypassing this phase avoids heavy Playwright contexts, drastically reducing RAM usage and preventing server crashes.

### 5. 🎨 Golden-Yellow & White Dashboard UI
* A premium, high-contrast gold/charcoal theme (Light Mode: crisp warm white; Dark Mode: golden charcoal) built with React + Vite + Tailwind CSS.

---

## 🛠️ Installation & Setup

### 1. Prerequisites
* **Python 3.10+**
* **Node.js & npm**
* **Google Chrome / Playwright Browsers**

### 2. Quick Setup
1. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```
2. Install Frontend React dependencies:
   ```bash
   cd frontend
   npm install
   ```

---

## ⚡ Execution

### 1. Run Everything (Backend + Frontend)
Double-click or run the startup batch script in the root directory:
```bash
run_servers.bat
```
This launches:
* **FastAPI Backend API** on `http://localhost:8000` (FastAPI orchestrator)
* **React Dashboard** on `http://localhost:3000` (Vite dev server)
In separate, color-coded Command Prompt windows for easy log monitoring.

### 2. Run Command Line Scraper (CLI)
You can also run the core engine directly from the command line:
```bash
python scraper.py --keywords "Dentist" --location "Mumbai" --pages 1 --headless
```
Report files are exported to the `./output` folder in both CSV (`results_*.csv`) and Excel (`report_*.xlsx`) formats.

---

## 📂 Project Architecture

* `scraper.py`: Core sector discovery, SERP extraction, and ATC verification engine.
* `main_api.py`: FastAPI backend wrapper communicating task status and results to the UI.
* `run_servers.bat`: Automated multi-server launch script.
* `frontend/`: React + Vite client dashboard.
* `output/`: Folder containing exported CSV and Excel reports.
