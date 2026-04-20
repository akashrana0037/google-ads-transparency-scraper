import argparse
import asyncio
import csv
import json
import logging
import os
import random
import re
import signal
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional
from urllib.parse import urlparse, unquote, quote

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Page, BrowserContext, Error as PlaywrightError
from tqdm import tqdm

class ProxyRotateException(Exception):
    """Raised to trigger a destruction and recreation of the Playwright browser using a new proxy."""
    pass

# ============================================================================
# 1. CONFIGURATION
# ============================================================================

CONFIG = {
    "selectors": {
        # ── Google Ads (2025/2026 multi-selector array — try each in order) ──
        # Google rotates class names; we use multiple fallbacks.
        "ad_block_css": [
            "[data-text-ad]",           # Most stable data attribute
            ".uEierd",                   # Top ad container
            ".vdQmEd",                   # Alternative top ad
            ".v5yQqb",                   # Bottom ad block
            "[aria-label='Ads']",        # Accessible label fallback
            "div:has([aria-label='Ad'])",
            "div:has([aria-label='Ads'])",
            "div:has([aria-label='Sponsored'])",
            ".commercial-unit-desktop-top",
            "#tads .commercial-unit",
            ".K6of9c",                   # 2025 variant
            ".a8Gq9e",                   # 2025 variant
        ],

        # Playwright locator for live DOM ad detection (JS-rendered)
        "ad_sponsored_label": "[aria-label='Sponsored'], [aria-label='Ad'], .x54gtf, .CbQPAb",
        # Organic results
        "organic": ".tF2Cxc, .g, div[data-hveid], .Ww4FFb, .MjjYud .g",
        "organic_title": "h3, .LC20lb, .vv77bd, .DKV0Md",
        # Ad field selectors (within an ad container)
        "ad_headline": "[role='heading'], h3, .CCgQ5, .v0nnCb, .qzEoUe",
        "ad_description": ".yDYNvb, .MUxGbd, .lyLwlc, .Va3FIb",
        "ad_displayed_link": ".dyS8sc, .q0v73c, .V9uS6c, .cxzHyb",
        "ad_company_name": ".hGSR34, .NJjxre, .LbUacb",
        # Local pack
        "local_item": "div.VkpGBb, div.uMdZh, div.C89n6b",
        "local_more_places": "a[aria-label^='More places'], .iY9M6",
        "local_sidebar": "div[data-hveid].commercial-unit-desktop-rhs, #rhs, .UDZeY",
        "result_link": "a[href]",
    },
    "delays": {
        "serp_min": 8,
        "serp_max": 20,
    },
    "timeouts": {
        "harvest_site": 15000, 
    },
    "user_agents": [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ],
    "viewports": [
        {"width": 1920, "height": 1080},
        {"width": 1366, "height": 768},
        {"width": 1440, "height": 900}
    ]
}

STEALTH_SCRIPTS = """
// 1. Mask WebDriver (Deep)
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
if (Object.getOwnPropertyDescriptor(Navigator.prototype, 'webdriver')) {
    delete Navigator.prototype.webdriver;
}

// 2. Mock Chrome Object
window.chrome = {
    app: { isInstalled: false, InstallState: { DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed' }, getDetails: () => {}, getIsInstalled: () => {} },
    runtime: { OnInstalledReason: { CHROME_UPDATE: 'chrome_update', INSTALL: 'install', SHARED_MODULE_UPDATE: 'shared_module_update', UPDATE: 'update' }, OnRestartRequiredReason: { APP_UPDATE: 'app_update', OS_UPDATE: 'os_update', PERIODIC: 'periodic' }, PlatformArch: { ARM: 'arm', ARM64: 'arm64', MIPS: 'mips', MIPS64: 'mips64', X86_32: 'x86-32', X86_64: 'x86-64' }, PlatformNaclArch: { ARM: 'arm', MIPS: 'mips', MIPS64: 'mips64', X86_32: 'x86-32', X86_64: 'x86-64' }, PlatformOs: { ANDROID: 'android', CROS: 'cros', LINUX: 'linux', MACOS: 'mac', OPENBSD: 'openbsd', WIN: 'win' }, RequestUpdateCheckStatus: { NO_UPDATE: 'no_update', THROTTLED: 'throttled', UPDATE_AVAILABLE: 'update_available' } },
    loadTimes: () => ({
        requestTime: Date.now() / 1000 - 0.5,
        startLoadTime: Date.now() / 1000 - 0.5,
        commitLoadTime: Date.now() / 1000 - 0.4,
        finishDocumentLoadTime: Date.now() / 1000 - 0.3,
        finishLoadTime: Date.now() / 1000 - 0.2,
        firstPaintTime: Date.now() / 1000 - 0.35,
        wasFetchedViaSpdy: true,
        wasAlternateProtocolAvailable: false,
        connectionInfo: "h2"
    }),
    csi: () => ({ startE: Date.now(), onloadT: Date.now() + 200, pageT: 2400.1, tran: 15 })
};

// 3. Spoof Permissions
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications' ?
    Promise.resolve({ state: Notification.permission }) :
    originalQuery(parameters)
);

// 4. Mimic Hardware/Memory Consistency
Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
Object.defineProperty(navigator, 'deviceMemory', { get: () => 16 });

// 5. Languages & Plugins
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
"""

# State structure template for reference
def get_initial_state():
    return {
        "run_meta": {},
        "competitors_found": [],
        "contacts_harvested": {},
        "atc_data": {}
    }

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Global state for signal handling (CLI only)
CHECKPOINT_STATE = get_initial_state()
CHECKPOINT_FILE = None

# ============================================================================
# 2. CHECKPOINT & STATE MANAGEMENT
# ============================================================================

def flush_checkpoint(state: dict, filepath: str):
    """Atomically saves the current execution state to disk."""
    if not filepath:
        return
    
    # Ensure directory exists before writing
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    
    tmp_file = f"{filepath}.tmp"
    try:
        with open(tmp_file, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2)
        os.replace(tmp_file, filepath)
    except Exception as e:
        logging.error(f"Failed to flush checkpoint: {e}")

def handle_interrupt(sig, frame):
    """Gracefully handles Ctrl+C by saving state before exiting."""
    logging.warning("\n[!] KeyboardInterrupt detected! Saving state and writing partial output...")
    
    run_meta = CHECKPOINT_STATE.get("run_meta", {})
    run_meta["status"] = "interrupted"
    CHECKPOINT_STATE["run_meta"] = run_meta
    flush_checkpoint(CHECKPOINT_STATE, CHECKPOINT_FILE)

    
    # Attempt to write partial CSV only if we have an output directory
    output_dir = run_meta.get("output_dir")
    if output_dir:
        export_csv(output_dir, partial=True)
    
    if CHECKPOINT_FILE:
        logging.info(f"State saved to {CHECKPOINT_FILE}.")
        logging.info(f"Resume command: python scraper.py --resume {CHECKPOINT_FILE}")
    sys.exit(2)

# signal.signal(signal.SIGINT, handle_interrupt) # MOVED TO MAIN BLOCK

# ============================================================================
# 3. SEMANTIC VARIANT ENGINE (New v6.0)
# ============================================================================

# ── INTENT TEMPLATES: Rich keyword expansion without needing Google ──────────
INTENT_TEMPLATES = {
    "commercial": [
        "best {sector} in {location}",
        "top {sector} {location}",
        "{sector} near me {location}",
        "affordable {sector} {location}",
        "professional {sector} services {location}",
        "cheap {sector} {location}",
    ],
    "brand": [
        "{sector} company {location}",
        "{sector} agency {location}",
        "{sector} firm {location}",
        "leading {sector} {location}",
        "top rated {sector} company {location}",
    ],
    "service": [
        "{sector} services {location}",
        "{sector} solutions {location}",
        "{sector} experts {location}",
        "{sector} consultants {location}",
        "hire {sector} {location}",
    ],
    "comparison": [
        "best {sector} companies {location}",
        "{sector} pricing {location}",
        "{sector} reviews {location}",
        "top 10 {sector} {location}",
    ],
}

def generate_keyword_variants(seed: str) -> List[str]:
    """Basic legacy variant generator (fallback only)."""
    variants = [seed]
    clean_seed = seed.lower().strip()
    variants.extend([f"best {clean_seed}", f"top {clean_seed}", f"{clean_seed} services"])
    return list(set(variants))

async def _fetch_google_autocomplete(sector: str, location: str) -> set:
    """
    Hits Google's Suggest API with Alphabet Soup expansion.
    Returns a set of raw suggestion strings.
    """
    import urllib.request
    suggestions = set()
    
    # ── Phase A: Standard Queries ──
    queries = [
        f"{sector} {location}",
        f"best {sector} {location}",
        f"top {sector} {location}",
        f"{sector} services {location}",
    ]
    
    # ── Phase B: Alphabet Soup (A-M for speed/coverage balance) ──
    # We use a subset of letters to keep it fast while still being "elite"
    for char in "abcde": 
        queries.append(f"{sector} {char}")

    for q in queries:
        try:
            url = f"https://suggestqueries.google.com/complete/search?client=firefox&q={quote(q)}&hl=en&gl=in"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                if isinstance(data, list) and len(data) > 1 and isinstance(data[1], list):
                    for s in data[1]:
                        if isinstance(s, str) and len(s) > 4:
                            suggestions.add(s)
        except Exception as e:
            logging.debug(f" [Autocomplete] Skipped '{q}': {e}")
    return suggestions

async def discover_elite_keywords(page: Page, sector: str, location: str, task_ref=None) -> List[str]:
    """
    Elite 5-Source Keyword Intelligence Engine.
    
    Sources (in priority order):
      1. Google Autocomplete API  — fast, no bot risk, high relevance
      2. Intent Template Generator — 20+ structured variants
      3. SERP PAA (People Also Ask) — question-intent keywords
      4. SERP Related Searches     — lateral semantic expansion
      5. Organic title mining       — location-specific ranking terms
    """
    if task_ref: task_ref.log(f"[Phase 0] Elite 5-Source Discovery → '{sector}' in '{location}'...")
    logging.info(f" [Intel] Starting 5-source keyword discovery for '{sector}' + '{location}'...")

    discovered = set()

    # ── SOURCE 1: Google Autocomplete (API — silent, no bot detection) ────────
    if task_ref: task_ref.log("  [1/5] Querying Google Autocomplete API...")
    try:
        autocomplete_results = await _fetch_google_autocomplete(sector, location)
        discovered.update(autocomplete_results)
        logging.info(f" [Intel] Autocomplete yielded {len(autocomplete_results)} suggestions.")
    except Exception as e:
        logging.warning(f" [!] Autocomplete API failed: {e}")

    # ── SOURCE 2: Intent Template Generator (always runs) ────────────────────
    if task_ref: task_ref.log("  [2/5] Generating intent-based keyword templates...")
    for category, templates in INTENT_TEMPLATES.items():
        for tpl in templates:
            kw = tpl.format(sector=sector, location=location)
            discovered.add(kw)
    logging.info(f" [Intel] Template engine added variants. Pool size: {len(discovered)}")

    # ── SOURCE 3+4+5: SERP scraping (PAA + Related + Organic titles) ─────────
    if task_ref: task_ref.log("  [3/5] Scraping SERP for PAA, Related, and Organic cues...")
    try:
        discovery_url = f"https://www.google.com/search?q={quote(sector + ' ' + location)}&gl=in&hl=en&num=10"
        await page.goto(discovery_url, wait_until="domcontentloaded", timeout=45000)
        await asyncio.sleep(random.uniform(2, 4))

        # Consent bypass
        page_title = await page.title()
        if "Before you continue" in page_title or "consent.google.com" in page.url:
            for btn_text in ["Accept all", "I agree", "Agree to all"]:
                try:
                    btn = page.get_by_role("button", name=re.compile(btn_text, re.I)).first
                    if await btn.is_visible(timeout=2000):
                        await btn.click()
                        await page.wait_for_load_state("domcontentloaded")
                        break
                except:
                    continue

        if "sorry.google.com" not in page.url:
            html = await page.content()
            soup = BeautifulSoup(html, 'lxml')

            # Source 3: PAA — People Also Ask (multiple selector variants for 2025-2026)
            paa_selectors = [
                ".dnXCYb", ".wQ6ne", "span[jsname]", ".CSY7u",
                "[data-q]", ".related-question-pair span"
            ]
            for sel in paa_selectors:
                for el in soup.select(sel):
                    txt = el.get_text(strip=True)
                    if txt and 8 < len(txt) < 120 and "?" in txt:
                        # Convert question to keyword: "What is X?" → "X"
                        clean = re.sub(r'^(what|where|how|which|who|why|when|is|are|do|can)\s+', '', txt.lower(), flags=re.I)
                        clean = re.sub(r'\?.*$', '', clean).strip()
                        if len(clean) > 5:
                            discovered.add(clean)

            # Source 4: Related Searches (multiple selector variants)
            related_selectors = [
                "a.ngTNl", "a.ggLgoc", ".s75CSd", ".k8XOCe",
                "a[data-query]", ".fKDtNb a", ".Bqq4Vd a"
            ]
            for sel in related_selectors:
                for el in soup.select(sel):
                    txt = el.get_text(strip=True)
                    if txt and 4 < len(txt) < 100:
                        discovered.add(txt)

            # Source 5: Organic title mining — grab titles with location signals
            loc_low = location.lower()
            for title_el in soup.select("h3, .LC20lb, .DKV0Md"):
                txt = title_el.get_text(strip=True).lower()
                if loc_low in txt and 5 < len(txt) < 100:
                    clean_t = re.split(r'[|\-–]', txt)[0].strip()
                    if len(clean_t) > 5:
                        discovered.add(clean_t)

            if task_ref: task_ref.log(f"  [✓] SERP mining done. Raw pool: {len(discovered)} terms.")
        else:
            if task_ref: task_ref.log("  [!] Google blocked SERP access. Using Autocomplete + Templates only.")

    except Exception as e:
        logging.warning(f" [!] SERP discovery hurdle (non-fatal, fallback active): {e}")

    # ── FINAL PROCESSING: Transactional Intent Scoring ──
    # Goal: Pick the top 20 "Perfect" transactional keywords
    scored_pool = []
    modifiers = ["buy", "best", "price", "cost", "professional", "services", "agency", "quote", "near me", "rating"]
    loc_low = location.lower()
    
    for kw in discovered:
        kw = kw.strip().lower()
        if not kw or len(kw) < 4: continue
        
        score = 0
        # Rule 1: Location relevance (High Priority)
        if loc_low in kw: score += 15
        
        # Rule 2: Transactional Intent Modifiers
        for mod in modifiers:
            if mod in kw: score += 10
            
        # Rule 3: Naturalness (exclude overly short/long strings)
        words = kw.split()
        if 2 <= len(words) <= 6: score += 5
        
        # Rule 4: Prefer the original sector name being present
        if sector.lower() in kw: score += 8
        
        scored_pool.append((score, kw))

    # Sort by score descending
    scored_pool.sort(key=lambda x: x[0], reverse=True)
    
    # Take top 20
    results = [item[1] for item in scored_pool[:20]]
    
    # Ensure raw seed is always included at the top if not present
    seed_kw = f"{sector} {location}".lower()
    if seed_kw not in results:
        results = [seed_kw] + results[:-1]

    if task_ref: task_ref.log(f" [✓] Final Intelligence Pool: 20 Elite High-Intent Keywords.")
    logging.info(f" [Intel] Selected top 20 transactional keywords: {results}")
    return results


# ============================================================================
# 4. EXTRACTION UTILITIES
# ============================================================================

def clean_domain(url: str) -> str:
    if not url or url.startswith('/'):
        return ""
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc
    except:
        return ""

def strip_tracking_params(url: str) -> str:
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        q = parse_qs_custom(parsed.query)
        # remove known tracking
        for block in ['gclid', 'gad_source', 'utm_source', 'utm_medium', 'utm_campaign']:
            q.pop(block, None)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    except:
        return url

def parse_qs_custom(query: str) -> dict:
    result = {}
    for pair in query.split('&'):
        if '=' in pair:
            k, v = pair.split('=', 1)
            result[k] = v
    return result

def extract_emails(text: str) -> set:
    emails = set()
    # Handle standard emails
    matches = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
    emails.update([m.lower() for m in matches])
    # Handle obfuscated e.g. info [at] domain dot com
    obf_matches = re.findall(r'([a-zA-Z0-9._%+-]+)\s*(?:\[at\]|\(at\)|\s+at\s+)\s*([a-zA-Z0-9.-]+)\s*(?:\[dot\]|\(dot\)|\s+dot\s+)\s*([a-zA-Z]{2,})', text, re.I)
    for m in obf_matches:
        emails.add(f"{m[0]}@{m[1]}.{m[2]}".lower())
    # Exclude image artifacts like .png, .jpg
    return {e for e in emails if not e.endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp'))}

def extract_phones(text: str) -> set:
    phones = set()
    # Indian context regex: +91, std codes, mobiles
    matches = re.findall(r'(?:\+?91[\-\s]?)?(?:\(?0\d{2,3}\)?[\-\s]?)?\d{3,4}[\-\s]?\d{3,4}[\-\s]?\d{3,4}', text)
    for p in matches:
        clean_p = re.sub(r'[^\d\+]', '', p)
        if 8 <= len(clean_p) <= 15:
            phones.add(clean_p)
    return phones

def extract_address(text: str) -> str:
    # Look for 6 digit pins Indian context
    text_clean = re.sub(r'\s+', ' ', text)
    match = re.search(r'(.{0,100}\d{6}.{0,50})', text_clean)
    if match:
        return match.group(1).strip()
    return ""

def extract_socials(html: str) -> dict:
    soup = BeautifulSoup(html, 'html.parser')
    socials = {'facebook': '', 'instagram': '', 'linkedin': '', 'twitter': '', 'youtube': ''}
    for a in soup.find_all('a', href=True):
        href = a['href']
        low_href = href.lower()
        if 'facebook.com' in low_href: socials['facebook'] = href
        elif 'instagram.com' in low_href: socials['instagram'] = href
        elif 'linkedin.com' in low_href: socials['linkedin'] = href
        elif 'twitter.com' in low_href or 'x.com' in low_href: socials['twitter'] = href
        elif 'youtube.com' in low_href: socials['youtube'] = href
    return socials

async def wait_for_captcha_resolution(page: Page, timeout_mins: int = 5) -> str:
    """
    Waits for the user to solve a CAPTCHA.
    Returns: "success", "timeout", or "closed"
    """
    logging.warning("\a") # Terminal Beep
    logging.warning("="*60)
    logging.warning(" [!] CAPTCHA DETECTED! ")
    logging.warning(f" Please solve the CAPTCHA in the browser window within {timeout_mins} minutes.")
    logging.warning(" The script will automatically resume once the block is cleared.")
    logging.warning("="*60)

    start_time = datetime.now(timezone.utc)
    while (datetime.now(timezone.utc) - start_time).total_seconds() < timeout_mins * 60:
        await asyncio.sleep(4)
        try:
            if page.is_closed():
                return "closed"
                
            html = await page.content()
            page_title = await page.title()
            current_url = page.url
            
            # Block detection
            still_blocked = (
                "sorry.google.com" in current_url or 
                "Before you continue" in page_title or 
                'id="captcha-form"' in html or 
                "unusual traffic from your computer network" in html
            )
            
            # Stronger success detection: Must NOT be blocked AND must have results or search box
            has_results = "#search" in html or 'name="q"' in html or "id=\"search\"" in html
            
            if not still_blocked and has_results:
                logging.info(" [✓] CAPTCHA cleared! Resuming scrape...")
                return "success"
                
        except PlaywrightError as e:
            if "closed" in str(e).lower():
                return "closed"
            logging.error(f"Transient error checking recovery: {e}")
        except Exception as e:
            logging.error(f"Unexpected error checking recovery: {e}")
            break
            
    return "timeout"

async def save_debug_dump(page: Page, output_dir: str, variant: str):
    """Saves page state for post-mortem analysis of failures."""
    debug_dir = os.path.join(output_dir, "debug")
    os.makedirs(debug_dir, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%H%M%S")
    clean_v = re.sub(r'[^\w\-]', '_', variant)
    
    try:
        # Save Screenshot
        ss_path = os.path.join(debug_dir, f"{clean_v}_{timestamp}.png")
        await page.screenshot(path=ss_path, timeout=5000)
        
        # Save HTML
        html_path = os.path.join(debug_dir, f"{clean_v}_{timestamp}.html")
        html = await page.content()
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        
        logging.info(f" [Debug] Saved diagnostic dump (SS+HTML) for variant '{variant}'")
    except Exception as e:
        logging.warning(f" [Debug] Failed to save dump: {e}")

# ============================================================================
# 4. GOOGLE SERP SCRAPING
# ============================================================================

async def _resolve_aclk_domain(page: Page, aclk_url: str) -> str:
    """
    Follows a Google /aclk redirect in a new tab to extract the real advertiser domain.
    Falls back to parsing the URL params directly.
    """
    # Try fast parse from URL params first (adurl= or q= param)
    for param in ['adurl', 'q', 'dest']:
        match = re.search(rf'[?&]{param}=([^&]+)', aclk_url)
        if match:
            try:
                raw = unquote(match.group(1))
                d = clean_domain(raw)
                if d and 'google' not in d:
                    return d
            except:
                pass
    # Fallback: navigate and capture final URL
    try:
        new_page = await page.context.new_page()
        await new_page.goto(aclk_url, wait_until="domcontentloaded", timeout=10000)
        final_url = new_page.url
        await new_page.close()
        d = clean_domain(final_url)
        if d and 'google' not in d:
            return d
    except:
        pass
    return ""


async def _extract_ads_from_live_dom(page: Page, variant: str, domain_map: dict, competitors: list, task_ref=None) -> int:
    """
    Primary ad extraction using Playwright's live DOM — catches JS-rendered ads
    that BeautifulSoup misses. Uses multiple selector strategies.
    """
    ads_found = 0

    # Strategy: Use multiple selector strategies from CONFIG
    strategy_selectors = CONFIG['selectors']['ad_block_css']


    seen_in_this_call = set()

    for css in strategy_selectors:
        try:
            ad_els = await page.query_selector_all(css)
            for ad_el in ad_els:
                try:
                    # Get outer HTML for BeautifulSoup parsing
                    ad_html = await ad_el.inner_html()
                    if not ad_html.strip():
                        continue

                    ad_soup = BeautifulSoup(ad_html, 'lxml')

                    # Extract all links — find the first non-google real domain
                    domain = ""
                    landing_url = ""
                    for a in ad_soup.find_all('a', href=True):
                        href = a['href']
                        if not href:
                            continue
                        if href.startswith('/aclk') or 'googleadservices' in href:
                            # Resolve the redirect
                            full_url = f"https://www.google.com{href}" if href.startswith('/') else href
                            domain = await _resolve_aclk_domain(page, full_url)
                            landing_url = full_url
                            if domain:
                                break
                        elif href.startswith('http') and 'google' not in href.lower():
                            d = clean_domain(href)
                            if d:
                                domain = d
                                landing_url = href
                                break

                    if not domain or domain in seen_in_this_call:
                        continue
                    seen_in_this_call.add(domain)

                    if domain in domain_map:
                        # Upgrade Organic/Local to Ad if encountered in an ad slot
                        existing = domain_map[domain]
                        if existing.get("result_type") != "Ad":
                            logging.info(f"   [Ad Upgrade] {domain} from {existing.get('result_type')} -> Ad")
                            existing["result_type"] = "Ad"
                            # Add missing ad details
                            existing["ad_headline"] = existing.get("ad_headline") or headline
                            existing["ad_description"] = existing.get("ad_description") or description
                            existing["displayed_link"] = existing.get("displayed_link") or displayed_link
                            existing["landing_page_url"] = landing_url or existing.get("landing_page_url")
                        
                        if variant not in existing.get('matched_keywords', []):
                            existing.setdefault('matched_keywords', []).append(variant)
                        continue


                    # Extract headline
                    headline = ""
                    for sel in CONFIG['selectors']['ad_headline'].split(', '):
                        node = ad_soup.select_one(sel.strip())
                        if node:
                            headline = node.get_text(strip=True)
                            break

                    # Extract description
                    description = ""
                    for sel in CONFIG['selectors']['ad_description'].split(', '):
                        node = ad_soup.select_one(sel.strip())
                        if node:
                            description = node.get_text(strip=True)
                            break

                    # Extract displayed link / company name
                    displayed_link = ""
                    for sel in CONFIG['selectors']['ad_displayed_link'].split(', '):
                        node = ad_soup.select_one(sel.strip())
                        if node:
                            displayed_link = node.get_text(strip=True)
                            break

                    company_name = displayed_link or headline or domain

                    comp = {
                        "result_type": "Ad",
                        "company_name": company_name,
                        "domain": domain,
                        "landing_page_url": landing_url,
                        "displayed_link": displayed_link,
                        "matched_keywords": [variant],
                        "ad_headline": headline,
                        "ad_description": description,
                    }
                    competitors.append(comp)
                    domain_map[domain] = comp
                    ads_found += 1
                    logging.info(f"   [Ad ✓] {domain} | '{headline[:50]}'")

                except Exception as e:
                    logging.debug(f"   [Ad parse error] {e}")
                    continue
        except Exception as e:
            logging.debug(f"   [Selector '{css}' failed] {e}")
            continue

    return ads_found


async def scrape_serp(page: Page, seed_keyword: str, max_pages: int, location: str, debug: bool, headless: bool, skip_captcha: bool, has_proxies: bool, task_ref=None, discovery_results: List[str] = None, state: dict = None, checkpoint_path: str = None):
    """
    Elite SERP Scraper v7.0 — Playwright-native ad extraction + organic/local harvesting.
    """
    variants = discovery_results if discovery_results else generate_keyword_variants(seed_keyword)
    competitors = state["competitors_found"]
    domain_map = {c['domain']: c for c in competitors}

    await page.set_extra_http_headers({"Accept-Language": "en-IN,en;q=0.9"})

    for v_idx, variant in enumerate(variants):
        if task_ref and task_ref.aborted:
            break
        if task_ref:
            task_ref.log(f"[{v_idx+1}/{len(variants)}] Scanning: '{variant}'")
        logging.info(f" [Target {v_idx+1}/{len(variants)}] '{variant}'")

        state["run_meta"]["active_variant"] = variant
        flush_checkpoint(state, checkpoint_path)

        for i in range(max_pages):
            if task_ref and task_ref.aborted:
                break

            logging.info(f"  Page {i+1}/{max_pages} for '{variant}'...")
            start_index = i * 10

            url = f"https://www.google.com/search?q={quote(variant)}&start={start_index}&gl=in&hl=en&num=10"

            # ── Human Path Simulation (V3 Innovation) ────────────────────
            # To avoid the "12-minute pattern block", we simulate a human typing the 
            # first page of each keyword instead of direct URL blasting.
            try:
                if i == 0:
                    # Start from root or previous page to establish 'Referer'
                    if page.url == "about:blank" or "google.com" not in page.url:
                        await page.goto("https://www.google.com", wait_until="domcontentloaded", timeout=30000)
                    
                    # Target the search box
                    search_box = await page.wait_for_selector('textarea[name="q"], input[name="q"]', timeout=5000)
                    if search_box:
                        await search_box.click()
                        # Select all and delete if text exists
                        await page.keyboard.press("Control+A")
                        await page.keyboard.press("Backspace")
                        # Type with random human intervals
                        await page.type('textarea[name="q"], input[name="q"]', variant, delay=random.uniform(50, 150))
                        await page.keyboard.press("Enter")
                        await page.wait_for_load_state("domcontentloaded", timeout=30000)
                    else:
                        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                else:
                    # For subsequent pages, direct URL is more acceptable, but we add a 'Thinking' delay
                    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            except Exception as e:
                logging.error(f"  Navigation Error (Retrying via URL Blast): {e}")
                try: await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                except: break

            await asyncio.sleep(random.uniform(2, 4))

            # ── Block / Consent Detection ──────────────────────────────────
            page_title = await page.title()

            if "Before you continue" in page_title or "consent.google.com" in page.url:
                logging.info("  [!] Consent page — attempting bypass...")
                for btn_text in ["Accept all", "I agree", "Agree to all"]:
                    try:
                        btn = page.get_by_role("button", name=re.compile(btn_text, re.I)).first
                        if await btn.is_visible(timeout=3000):
                            await btn.click()
                            await page.wait_for_load_state("domcontentloaded", timeout=10000)
                            break
                    except:
                        continue
            
            # Check for CAPTCHA (Graceful Recovery Mode)
            if "google.com/sorry" in page.url or "captcha" in (await page.content()).lower():
                if skip_captcha:
                    # In API mode, we DON'T crash. We log the block and RETURN to allow Analysis phases to run.
                    logging.warning(f" [!] PERSISTENT BLOCK for '{variant}'. Moving to Analysis Phase with existing data...")
                    if task_ref: task_ref.log(f"⚠️ Google block detected for '{variant}'. Transitioning to Intel Harvesting.")
                    return # Exit scrape_serp gracefully
                else:
                    res = await wait_for_captcha_resolution(page)
                    if res != "success":
                        logging.warning(f"  CAPTCHA/Block for '{variant}'. Skipping variant.")
                        break

            # ── Scroll to trigger lazy-loaded bottom ads ───────────────────
            try:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
                await asyncio.sleep(0.8)
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(1.2)
                await page.evaluate("window.scrollTo(0, 0)")  # Back to top
                await asyncio.sleep(0.5)
            except:
                pass

            results_this_page = 0

            # ── PHASE 1: AD EXTRACTION (Playwright live DOM) ───────────────
            ads_count = await _extract_ads_from_live_dom(page, variant, domain_map, competitors, task_ref)
            results_this_page += ads_count
            if task_ref and ads_count > 0:
                task_ref.log(f"   ↳ Ads captured: {ads_count}")
            logging.info(f"  [Ads] Extracted {ads_count} ad leads.")

            # ── PHASE 2: LOCAL PACK ───────────────────────────────────────
            await expand_local_results(page, task_ref)
            html = await page.content()
            soup = BeautifulSoup(html, 'lxml')

            local_count = 0
            for local in soup.select(CONFIG['selectors']['local_item']):
                link = local.select_one(CONFIG['selectors']['result_link'])
                if not link:
                    continue
                domain = clean_domain(link.get('href', ''))
                if not domain or 'google' in domain:
                    continue

                if domain in domain_map:
                    if variant not in domain_map[domain].get('matched_keywords', []):
                        domain_map[domain].setdefault('matched_keywords', []).append(variant)
                    continue

                title_node = local.select_one('.OSrXXb, .qBF1Pd, .dbg0pd')
                comp = {
                    "result_type": "Local",
                    "company_name": title_node.get_text(strip=True) if title_node else domain,
                    "domain": domain,
                    "landing_page_url": link.get('href', ''),
                    "displayed_link": domain,
                    "matched_keywords": [variant],
                    "ad_headline": "",
                    "ad_description": "",
                }
                competitors.append(comp)
                domain_map[domain] = comp
                local_count += 1
            results_this_page += local_count
            logging.info(f"  [Local] Extracted {local_count} local leads.")

            # ── PHASE 3: ORGANIC ─────────────────────────────────────────
            organic_count = 0
            for orig in soup.select(CONFIG['selectors']['organic']):
                link = orig.select_one(CONFIG['selectors']['result_link'])
                if not link:
                    continue
                raw_href = link.get('href', '')
                if not raw_href.startswith('http'):
                    continue
                domain = clean_domain(raw_href)
                if not domain or 'google' in domain:
                    continue

                if domain in domain_map:
                    if variant not in domain_map[domain].get('matched_keywords', []):
                        domain_map[domain].setdefault('matched_keywords', []).append(variant)
                    continue

                title_node = orig.select_one(CONFIG['selectors']['organic_title'])
                comp = {
                    "result_type": "Organic",
                    "company_name": title_node.get_text(strip=True) if title_node else domain,
                    "domain": domain,
                    "landing_page_url": raw_href,
                    "displayed_link": domain,
                    "matched_keywords": [variant],
                    "ad_headline": "",
                    "ad_description": "",
                }
                competitors.append(comp)
                domain_map[domain] = comp
                organic_count += 1
            results_this_page += organic_count
            logging.info(f"  [Organic] Extracted {organic_count} organic leads.")

            # ── Checkpoint & Progress ─────────────────────────────────────
            state["run_meta"]["pages_completed"] = i + 1
            state["competitors_found"] = competitors
            flush_checkpoint(state, checkpoint_path)

            if task_ref:
                task_ref.results_count = len(competitors)

            if results_this_page == 0:
                logging.warning(f"  [!] Zero results on page {i+1} for '{variant}'. Saving debug dump.")
                await save_debug_dump(page, state["run_meta"]["output_dir"], variant)
                break

            # Human-like delay between pages (Modified for v2 Stealth)
            delay = random.uniform(12, 28)
            logging.info(f"  [Stealth] Waiting {delay:.1f}s before next page...")
            await asyncio.sleep(delay)

    # Cool-down to reset Google's behavioral score
    p_delay = random.uniform(20, 45)
    logging.info(f" [Mission Control] Sector Scrape Complete. Resting for {p_delay:.1f}s to preserve identity...")
    await asyncio.sleep(p_delay)
    
    state["run_meta"]["active_variant"] = "Harvesting Deep Intel..."
    flush_checkpoint(state, checkpoint_path)


# ============================================================================
# 5. CONTACT HARVESTING
# ============================================================================

async def harvest_single_domain(context: BrowserContext, comp: dict, sem: asyncio.Semaphore, state: dict, checkpoint_path: str):
    """Visits homepage and /contact, extracts raw text and merges insights."""
    domain = comp["domain"]
    if domain in state["contacts_harvested"]:
        return # Skip already harvested
    
    contact_data = {
        "emails": set(),
        "phones": set(),
        "address": "",
        "social": {'facebook': '', 'instagram': '', 'linkedin': '', 'twitter': '', 'youtube': ''},
        "contact_page_url": "",
        "scrape_status": "Error"
    }
    
    page = None
    try:
        async with sem:
            try:
                page = await context.new_page()
                await page.add_init_script(STEALTH_SCRIPTS)
            except Exception as e:
                logging.error(f" [Harvest] Page creation failed for {domain}: {e}")
                contact_data["scrape_status"] = "Browser Crash"
                return

            # 1. Homepage Visit
            homepage_url = f"https://{domain}"
            resp = await page.goto(homepage_url, timeout=CONFIG['timeouts']['harvest_site'], wait_until="domcontentloaded")
            
            if resp and resp.status in [403, 401]:
                contact_data["scrape_status"] = "Blocked"
            else:
                contact_data["scrape_status"] = "Success"
                
                # Extract details
                html = await page.content()
                text = await page.evaluate("() => document.body ? document.body.innerText : ''")
                
                contact_data["emails"].update(extract_emails(text))
                contact_data["emails"].update(extract_emails(html)) # Mailto links
                contact_data["phones"].update(extract_phones(text))
                contact_data["address"] = extract_address(text)
                
                new_socials = extract_socials(html)
                for k in new_socials:
                    if new_socials[k]: contact_data["social"][k] = new_socials[k]

                # 2. Contact/About/Services Page Deep-Crawl
                crawl_targets = await page.evaluate('''() => {
                    const links = Array.from(document.querySelectorAll('a'));
                    return links
                        .filter(l => {
                            const t = l.innerText.toLowerCase();
                            const h = l.href ? l.href.toLowerCase() : "";
                            return t.includes('contact') || h.includes('contact') ||
                                   t.includes('about') || h.includes('about') ||
                                   t.includes('service') || h.includes('service');
                        })
                        .map(l => l.href)
                        .filter((v, i, a) => a.indexOf(v) === i) // Unique
                        .slice(0, 3); // Max 3 deep pages to avoid bloat
                }''')
                
                for target_url in crawl_targets:
                    if not target_url.startswith('http'): continue
                    try:
                        await page.goto(target_url, timeout=10000, wait_until="domcontentloaded")
                        curr_html = await page.content()
                        curr_text = await page.evaluate("() => document.body ? document.body.innerText : ''")
                        
                        contact_data["emails"].update(extract_emails(curr_text))
                        contact_data["emails"].update(extract_emails(curr_html))
                        contact_data["phones"].update(extract_phones(curr_text))
                        if not contact_data["address"]:
                            contact_data["address"] = extract_address(curr_text)
                            
                        # Refresh social leads
                        new_socials = extract_socials(curr_html)
                        for k in new_socials:
                            if new_socials[k]: contact_data["social"][k] = new_socials[k]
                    except:
                        continue
                    
    except PlaywrightError as e:
        if "Timeout" in str(e):
            contact_data["scrape_status"] = "Timeout"
        else:
            contact_data["scrape_status"] = "Error"
    except Exception as e:
        contact_data["scrape_status"] = "Error"
    finally:
        if page:
            await page.close()
        
        # Convert sets to lists for JSON serialization
        contact_data["emails"] = sorted(list(contact_data["emails"]))
        contact_data["phones"] = sorted(list(contact_data["phones"]))
        
        state["contacts_harvested"][domain] = contact_data
        flush_checkpoint(state, checkpoint_path)

async def harvest_all_contacts(context: BrowserContext, concurrency: int, state: dict, checkpoint_path: str, task_ref=None):
    """Driver for parallel site visiting."""
    competitors = state["competitors_found"]
    pending = [c for c in competitors if c["domain"] not in state["contacts_harvested"]]
    
    if not pending:
        logging.info("All contacts harvested from checkpoint. Skipping.")
        return

    logging.info(f"Harvesting contact info for {len(pending)} domains (Concurrency= {concurrency})...")
    sem = asyncio.Semaphore(concurrency)
    
    tasks = [harvest_single_domain(context, comp, sem, state, checkpoint_path) for comp in pending]
    
    # Run loop with progress bar
    for f in tqdm(asyncio.as_completed(tasks), total=len(tasks), desc="Harvesting Sites"):
        if task_ref and task_ref.aborted:
            logging.info(" [!] Abort detected during harvesting. Terminating workers...")
            break
        await f

# ============================================================================
# 6. ADS TRANSPARENCY ENRICHMENT (ANONYMOUS)
# ============================================================================

async def verify_atc_data(context: BrowserContext, domain: str, sem: asyncio.Semaphore, state: dict, checkpoint_path: str):
    """Searches Google Ads Transparency Center for a domain/advertiser."""
    if domain in state["atc_data"]:
        return
        
    async with sem:
        atc_item = {
            "advertiser_id": "N/A",
            "verified_name": "Not Found",
            "active_ads": "0",
            "status": "Error"
        }
        
        page = None
        try:
            # Step 0: Ensure page is alive
            try:
                page = await context.new_page()
                await page.add_init_script(STEALTH_SCRIPTS)
            except Exception as e:
                logging.error(f" [ATC] Page creation failed for {domain}: {e}")
                atc_item["status"] = "Browser Crash"
                return

            # Step 1: Navigation
            url = f"https://adstransparency.google.com/?region=IN&domain={quote(domain)}"
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(3) # Let SPA settle
            
            # Step 1: Type Domain into search box
            search_box = "input.input-area"
            await page.wait_for_selector(search_box, timeout=10000)
            await page.click(search_box)
            await page.fill(search_box, domain)
            await asyncio.sleep(5) # Wait for dropdown
            
            # Step 2: Detect first 'Advertiser' result in dropdown
            dropdown_item = "material-select-item.item"
            try:
                await page.wait_for_selector(dropdown_item, timeout=8000)
                # Click the first match
                await page.click(dropdown_item)
                
                # IMPORTANT: Wait for the URL to change to the profile page
                # e.g., adstransparency.google.com/advertiser/AR...
                try:
                    await page.wait_for_url(re.compile(r".*/advertiser/.*"), timeout=15000)
                except:
                    logging.debug(f" [ATC] Timeout waiting for URL change for '{domain}'. Continuing...")
                
                await asyncio.sleep(5) # Final SPA settle
                
                # Step 3: Extract Data from Profile Page
                current_url = page.url
                # Extract ID from URL path: .../advertiser/AR16638892... or .../agency/AR166...
                id_match = re.search(r'/(?:advertiser|agency)/([^?&/]+)', current_url)
                if not id_match:
                    # Retry once after a short wait if we are on a result page but URL hasn't settled
                    await asyncio.sleep(2)
                    id_match = re.search(r'/(?:advertiser|agency)/([^?&/]+)', page.url)
                
                if id_match:
                    atc_item["advertiser_id"] = id_match.group(1)
                
                # Extract Verified Name (New Selector)
                name_node = await page.query_selector("span.advertiser-name.current-scope")
                if not name_node:
                    name_node = await page.query_selector("div.legal-name")
                if not name_node:
                    name_node = await page.query_selector(".grid-info .name")
                    
                if name_node:
                    atc_item["verified_name"] = (await name_node.inner_text()).strip()
                
                # Extract Ad Count (New Selector)
                count_node = await page.query_selector("div.ads-count")
                if not count_node:
                    count_node = await page.query_selector(".grid-info .left-repo")
                    
                if count_node:
                    atc_item["active_ads"] = (await count_node.inner_text()).strip()
                
                atc_item["status"] = "Found"
                logging.info(f" [ATC] Verified '{domain}' -> {atc_item['verified_name']} | ID: {atc_item['advertiser_id']} ({atc_item['active_ads']})")
                
            except Exception as e:
                atc_item["status"] = "Error"
                logging.debug(f" [ATC] Parsing failure for '{domain}': {e}")

        except Exception as e:
            atc_item["status"] = "Error"
            logging.debug(f" [ATC] Failure checking '{domain}': {e}")
        finally:
            if page:
                await page.close()
            state["atc_data"][domain] = atc_item
            flush_checkpoint(state, checkpoint_path)

async def enrich_all_atc(browser, concurrency: int = 2, state: dict = None, checkpoint_path: str = None, task_ref=None):
    """Driver for ATC Enrichment Phase."""
    competitors = state["competitors_found"]
    # Focus on domains not yet checked in ATC
    pending = [c["domain"] for c in competitors if c["domain"] not in state["atc_data"]]
    
    if not pending:
        logging.info("All domains already enriched via ATC. Skipping.")
        return

    logging.info(f"Enriching data via Ads Transparency Center for {len(pending)} domains...")
    sem = asyncio.Semaphore(concurrency)
    
    context = await browser.new_context(user_agent=random.choice(CONFIG["user_agents"]))
    await context.add_init_script(STEALTH_SCRIPTS)
    
    tasks = [verify_atc_data(context, domain, sem, state, checkpoint_path) for domain in pending]
    
    for f in tqdm(asyncio.as_completed(tasks), total=len(tasks), desc="ATC Verification"):
        if task_ref and task_ref.aborted:
            logging.info(" [!] Abort detected during ATC enrichment. Terminating workers...")
            break
        await f
    
    await context.close()

# ============================================================================
# 7. CSV OUTPUT
# ============================================================================

def export_csv(state: dict, output_dir: str, partial: bool = False):
    """Writes results to CSV."""
    run_meta = state.get("run_meta", {})
    comps = state.get("competitors_found", [])
    contacts = state.get("contacts_harvested", {})
    
    if not comps:
        logging.warning("No competitors found to export.")
        return
    
    timestamp = run_meta.get("started_at", "unknown").replace(":", "").replace("-", "").replace("T", "_")[:15]
    suffix = "_PARTIAL" if partial else ""
    filename = f"results_{timestamp}{suffix}.csv"
    filepath = os.path.join(output_dir, filename)
    
    # Ensure directory exists before writing
    os.makedirs(output_dir, exist_ok=True)
    
    headers = [
        "search_date", "search_keywords", "search_location", "result_type",
        "company_name", "domain", "landing_page_url", "displayed_link",
        "ad_headline", "ad_description", "emails", "phones", "address",
        "facebook", "instagram", "linkedin", "twitter", "youtube",
        "atc_verified_name", "atc_advertiser_id", "atc_active_ads",
        "contact_page_url", "scrape_status", "scraped_at"
    ]
    
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        
        for c in comps:
            domain = c["domain"]
            atc = state["atc_data"].get(domain, {
                "verified_name": "N/A", "advertiser_id": "N/A", "active_ads": "0"
            })
            
            # FILTER: Only export companies identified as active advertisers
            # (Either caught in SERP as an Ad OR verified via ATC as having >0 ads)
            is_serp_ad = c.get("result_type") == "Ad"
            is_atc_advertiser = atc.get("active_ads") not in ["0", "N/A", "Not Found", ""]
            
            if not (is_serp_ad or is_atc_advertiser):
                continue


            harvest = contacts.get(domain, {
                 "emails": [], "phones": [], "address": "",
                 "social": {'facebook': '', 'instagram': '', 'linkedin': '', 'twitter': '', 'youtube': ''},
                 "contact_page_url": "", "scrape_status": ""
            })
            
            atc = state["atc_data"].get(domain, {
                "verified_name": "N/A", "advertiser_id": "N/A", "active_ads": "N/A"
            })
            
            row = {
                "search_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "search_keywords": run_meta.get("keywords", "N/A"),
                "search_location": run_meta.get("location", "N/A"),
                "result_type": c["result_type"],
                "company_name": c["company_name"],
                "domain": domain,
                "landing_page_url": c.get("landing_page_url", ""),
                "displayed_link": c.get("displayed_link", ""),
                "ad_headline": c.get("ad_headline", ""),
                "ad_description": c.get("ad_description", ""),
                "emails": ";".join(harvest["emails"]),
                "phones": ";".join(harvest["phones"]),
                "address": harvest["address"],
                "facebook": harvest["social"]["facebook"],
                "instagram": harvest["social"]["instagram"],
                "linkedin": harvest["social"]["linkedin"],
                "twitter": harvest["social"]["twitter"],
                "youtube": harvest["social"]["youtube"],
                "atc_verified_name": atc["verified_name"],
                "atc_advertiser_id": atc["advertiser_id"],
                "atc_active_ads": atc["active_ads"],
                "contact_page_url": harvest["contact_page_url"],
                "scrape_status": harvest["scrape_status"],
                "scraped_at": datetime.now(timezone.utc).isoformat()
            }
            writer.writerow(row)
            
    logging.info(f"Successfully wrote {len(comps)} records to {filepath}")

# ============================================================================
# 8. AUTONOMOUS RUNNER (API COMPATIBLE)
# ============================================================================

async def run_autonomous_scrape(keywords: str, location: str, pages: int, checkpoint_file: str, output_dir: str, task_ref=None, headless: bool = True):
    """
    Programmatic entry point for the scraper (API).
    Returns basic run info upon completion.
    """
    # Create isolated initial state for this specific run
    state = get_initial_state()
    
    state["run_meta"] = {
        "keywords": keywords,
        "location": location,
        "max_pages": pages,
        "output_dir": output_dir,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "status": "running",
        "pages_completed": 0
    }
    # Ensure directory exists before first checkpoint
    os.makedirs(output_dir, exist_ok=True)
    flush_checkpoint(state, checkpoint_file)
    
    # Determine if we have a saved session to bypass CAPTCHA
    session_dir = "google_session"
    has_session = os.path.exists(session_dir)
    
    # Resource Management: Track everything for final cleanup
    resources = {
        "browser_main": None,
        "browser_harvest": None,
        "context_main": None,
        "context_contacts": None
    }

    try:
        async with async_playwright() as p:
            # ── Phase 0: Discovery & Approval ────────────────────────────
            selected_ua = random.choice(CONFIG["user_agents"])
            selected_vp = random.choice(CONFIG["viewports"])

            if has_session:
                resources["context_main"] = await p.chromium.launch_persistent_context(
                    user_data_dir=os.path.abspath(session_dir),
                    headless=headless, user_agent=selected_ua, viewport=selected_vp,
                    ignore_https_errors=True, bypass_csp=True,
                    args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
                )
            else:
                resources["browser_main"] = await p.chromium.launch(headless=headless)
                resources["context_main"] = await resources["browser_main"].new_context(user_agent=selected_ua, viewport=selected_vp)
            
            await resources["context_main"].add_init_script(STEALTH_SCRIPTS)
            page_main = resources["context_main"].pages[0] if resources["context_main"].pages else await resources["context_main"].new_page()

            if task_ref: 
                task_ref.status = "discovering_keywords"
                task_ref.log("Phase 0/3: Executing Elite Sector Discovery...")
            
            discovery_keywords = await discover_elite_keywords(page_main, keywords, location, task_ref)
            
            if task_ref:
                task_ref.discovered_keywords = discovery_keywords
                task_ref.status = "awaiting_approval"
                task_ref.log(f"Phase 0/3 Complete. Discovered {len(discovery_keywords)} targets.")
                task_ref.log("SYSTEM IDLE: Awaiting user selection/approval...")
                await task_ref.approval_event.wait()
                discovery_keywords = task_ref.discovered_keywords
                task_ref.status = "scraping_serp"
                task_ref.log(f"Phase 1/3: Scraping SERP for {len(discovery_keywords)} variants...")

            # ── Phase 1: Robust SERP Scrape (with Self-Healing Loop) ──────
            while state["run_meta"]["pages_completed"] < pages:
                try:
                    # If browser/context is missing (first run or after crash), create it
                    if not resources["context_main"]:
                        selected_ua = random.choice(CONFIG["user_agents"])
                        selected_vp = random.choice(CONFIG["viewports"])

                        if has_session:
                            logging.info(f" [API] Identity Restore: Launching with persistent cache...")
                            resources["context_main"] = await p.chromium.launch_persistent_context(
                                user_data_dir=os.path.abspath(session_dir),
                                headless=headless,
                                user_agent=selected_ua,
                                viewport=selected_vp,
                                ignore_https_errors=True,
                                bypass_csp=True,
                                args=['--disable-blink-features=AutomationControlled', '--no-sandbox', '--disable-setuid-sandbox']
                            )
                        else:
                            logging.info(f" [API] Identity Shift: Launching fresh stealth context...")
                            resources["browser_main"] = await p.chromium.launch(headless=headless)
                            resources["context_main"] = await resources["browser_main"].new_context(user_agent=selected_ua, viewport=selected_vp)
                        
                        await resources["context_main"].add_init_script(STEALTH_SCRIPTS)
                    
                    page_main = resources["context_main"].pages[0] if resources["context_main"].pages else await resources["context_main"].new_page()
                    
                    # Execute Scrape
                    await scrape_serp(page_main, keywords, pages, location, False, headless, True, False, task_ref, discovery_results=discovery_keywords, state=state, checkpoint_path=checkpoint_file)
                    
                    # If we reached here without error, the SERP phase is finished or we ended gracefully (return).
                    break 

                except Exception as e:
                    logging.warning(f" [Self-Heal] Mission turbulence detected: {e}. Re-orienting identity...")
                    if task_ref: task_ref.log(f"⚠️ Interface reset. Attempting to bypass block...")
                    
                    # Cleanup previous context
                    if resources["context_main"]: await resources["context_main"].close()
                    if resources["browser_main"]: await resources["browser_main"].close()
                    resources["context_main"] = None
                    resources["browser_main"] = None
                    
                    # Exponential Backoff
                    await asyncio.sleep(random.uniform(5, 10))
                    # Loop will continue and recreate context

            # Close SERP context to free RAM before Harvesting
            if resources["context_main"]: await resources["context_main"].close()
            if resources["browser_main"]: await resources["browser_main"].close()
            resources["context_main"] = None
            resources["browser_main"] = None

            # Phase 2: Harvesting
            if task_ref:
                task_ref.status = "harvesting_contacts"
                task_ref.log("Phase 2/3: Harvesting contact details...")
            
            resources["browser_harvest"] = await p.chromium.launch(headless=True)
            resources["context_contacts"] = await resources["browser_harvest"].new_context(user_agent=random.choice(CONFIG["user_agents"]))
            await resources["context_contacts"].add_init_script(STEALTH_SCRIPTS)
            
            await harvest_all_contacts(resources["context_contacts"], 5, state=state, checkpoint_path=checkpoint_file, task_ref=task_ref) 
            await resources["context_contacts"].close()
            
            # Phase 3: ATC
            if task_ref:
                task_ref.status = "verifying_ads"
                task_ref.log("Phase 3/3: Verifying Ad Transparency Registry...")
            
            await enrich_all_atc(resources["browser_harvest"], concurrency=2, state=state, checkpoint_path=checkpoint_file, task_ref=task_ref)
            await resources["browser_harvest"].close()
            
            # Finalize
            state["run_meta"]["status"] = "completed"
            flush_checkpoint(state, checkpoint_file)
            export_csv(state, output_dir, partial=False)
            
            filename = "results_" + state["run_meta"]["started_at"].replace(":", "").replace("-", "").replace("T", "_")[:15] + ".csv"
            final_results = []
            for r in state["competitors_found"]:
                d = r["domain"]
                atc_info = state["atc_data"].get(d, {})
                is_serp_ad = r.get("result_type") == "Ad"
                is_atc_advertiser = atc_info.get("active_ads") not in ["0", "N/A", "Not Found", ""]
                if is_serp_ad or is_atc_advertiser:
                    final_results.append(r)
                    
            return {"csv_file": os.path.join(output_dir, filename), "results": final_results}



    except asyncio.CancelledError:
        logging.warning(" [!] Task was CANCELLED. Cleaning up...")
        state["run_meta"]["status"] = "aborted"
        flush_checkpoint(state, checkpoint_file)
        # Emergency Save
        export_csv(state, output_dir, partial=True)
        raise 
    except Exception as e:
        logging.error(f"API Scrape failed: {e}")
        state["run_meta"]["status"] = "failed"
        state["run_meta"]["error"] = str(e)
        flush_checkpoint(state, checkpoint_file)
        export_csv(state, output_dir, partial=True)
        raise e
    finally:
        # Absolute Resource Cleanup
        logging.info(" [Cleanup] Closing all mission-specific browsers...")
        for res in resources.values():
            try:
                if res: await res.close()
            except: pass

# ============================================================================
# 9. MAIN ORCHESTRATION (CLI)
# ============================================================================

async def expand_local_results(page: Page, task_ref=None):
    """Detects and expands the 'More places' section if available, scrolling the sidebar."""
    try:
        more_places = await page.query_selector(CONFIG['selectors']['local_more_places'])
        if more_places:
            if task_ref: task_ref.log("Local Pack Detected. Initiating Deep-Dive Expansion...")
            logging.info("Deep-Dive Expansion: More places button found. Clicking...")
            await more_places.click()
            await page.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(random.uniform(3, 5))
            
            # Identify the scrollable sidebar
            sidebar = await page.query_selector(CONFIG['selectors']['local_sidebar'])
            if sidebar:
                logging.info("Local Sidebar expansion started. Scrolling to reveal hidden competitors...")
                # Scroll a few times to get more results (e.g., 3-4 scroll cycles)
                for s in range(3):
                    if task_ref and task_ref.aborted: break
                    await sidebar.evaluate("el => el.scrollTop = el.scrollHeight")
                    await asyncio.sleep(random.uniform(2, 3))
                    if task_ref: task_ref.log(f"Deep-Dive: Scrolled Local Panel ({s+1}/3)")
                
                # Check for 'Next' button if any, or just take what we have
                return True
        return False
    except Exception as e:
        logging.warning(f"Local expansion failed (possibly already on page): {e}")
        return False

async def main():
    global CHECKPOINT_STATE, CHECKPOINT_FILE
    state = get_initial_state()
    parser = argparse.ArgumentParser(description="Autonomous Google Ads Competitor Scraper")
    parser.add_argument("--keywords", type=str, help="Search query string")
    parser.add_argument("--location", type=str, default="India", help="Target location")
    parser.add_argument("--pages", type=int, default=4, help="Number of SERP pages to scrape")
    parser.add_argument("--output", type=str, default="./output", help="Output directory")
    parser.add_argument("--concurrency", type=int, default=5, help="Concurrent domain visits limit")
    parser.add_argument("--proxy", type=str, help="HTTP/HTTPS proxy string")
    parser.add_argument("--proxy-list", type=str, help="Path to txt file containing one proxy per line")
    parser.add_argument("--debug", action="store_true", help="Save raw SERP dumps for debugging")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode (no browser window)")
    parser.add_argument("--resume", type=str, help="Path to JSON checkpoint file to resume")
    parser.add_argument("--skip-captcha", action="store_true", help="Automatically rotate proxy on CAPTCHA instead of waiting for manual solve")
    parser.add_argument("--login", action="store_true", help="Launch browser to manually log into your Google account for a trusted session")
    parser.add_argument("--session-dir", type=str, default="./google_session", help="Path to folder for storing your persistent Google session/cookies")
    
    args = parser.parse_args()
    os.makedirs(args.output, exist_ok=True)
    
    if args.login:
        logging.info(" [!] LOGIN MODE ACTIVE. Starting browser for manual Google sign-in...")
        async with async_playwright() as p:
            # Use persistent context to save login
            context = await p.chromium.launch_persistent_context(
                user_data_dir=args.session_dir,
                headless=False,
                args=["--disable-blink-features=AutomationControlled"]
            )
            page = context.pages[0]
            await page.goto("https://accounts.google.com")
            logging.info("="*60)
            logging.info(" [ACTION REQUIRED] Please log into your Gmail account now.")
            logging.info(" Once you are successfully signed in, you can close the browser window.")
            logging.info("="*60)
            
            # Wait for user to close browser or timeout
            try:
                while not context.browser.is_connected() or len(context.pages) > 0:
                    await asyncio.sleep(5)
            except: pass
            logging.info(" [✓] Login session saved. You can now run the scraper normally.")
            return

    checkpoint_path = ""
    state = get_initial_state()

    if args.resume:
        checkpoint_path = args.resume
        with open(args.resume, "r", encoding="utf-8") as f:
            state = json.load(f)
        CHECKPOINT_STATE = state
        CHECKPOINT_FILE = checkpoint_path
        logging.info(f"Resuming run from {checkpoint_path}")
        state["run_meta"]["status"] = "running"
    else:
        if not args.keywords:
            parser.error("--keywords is required unless using --resume")
        
        timestamp = datetime.now(timezone.utc).isoformat().replace(":", "").replace("-", "")[:15]
        checkpoint_path = os.path.join(args.output, f"checkpoint_{timestamp}.json")
        state["run_meta"] = {
            "keywords": args.keywords,
            "location": args.location,
            "max_pages": args.pages,
            "output_dir": args.output,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "status": "running",
            "pages_completed": 0
        }
        flush_checkpoint(state, checkpoint_path)
        CHECKPOINT_FILE = checkpoint_path
        CHECKPOINT_STATE = state
        logging.info(f"Starting new run. Checkpoint: {checkpoint_path}")

    proxy_pool = []
    if args.proxy_list and os.path.exists(args.proxy_list):
        with open(args.proxy_list, "r", encoding="utf-8") as f:
            proxy_pool = [line.strip() for line in f if line.strip()]
    elif args.proxy:
        proxy_pool = [args.proxy]
        
    val_keys = state["run_meta"]["keywords"]
    val_pages = state["run_meta"]["max_pages"]
    val_loc = state["run_meta"]["location"]

    # Launch Playwright Environment
    async with async_playwright() as p:
        while True:
            # 1. Verification: Is there anything left in the pool?
            if not proxy_pool and (args.proxy_list or args.proxy):
                logging.error(" [!] ALL PROXIES EXHAUSTED. Terminal execution stopped. Please provide fresh IPs.")
                sys.exit(3)

            # 2. Check if SERP phase is already complete
            if state["run_meta"]["pages_completed"] >= val_pages:
                break
                
            browser_args = {
                "headless": args.headless,
                "user_agent": random.choice(CONFIG["user_agents"]),
                "args": ["--disable-blink-features=AutomationControlled"]
            }
            
            current_proxy = proxy_pool[0] if proxy_pool else None
            if current_proxy:
                browser_args["proxy"] = {"server": current_proxy}
            
            has_proxies = len(proxy_pool) > 0
            context = None
            try:
                # Use Persistent Context for session reuse (Gmail login)
                context = await p.chromium.launch_persistent_context(
                    user_data_dir=args.session_dir,
                    **browser_args
                )
                
                # Apply Stealth Scripts
                await context.add_init_script(STEALTH_SCRIPTS)
                
                # If no pages exist in persistent context, create one
                page = context.pages[0] if context.pages else await context.new_page()
                
                # ── Phase 0: DISCOVERY (New CLI Feature) ──
                logging.info(f" [Phase 0] Analyzing sector: '{val_keys}'...")
                discovery_keywords = await discover_elite_keywords(page, val_keys, val_loc)
                
                # ── Phase 1-3: FULL MISSION ──
                await scrape_serp(page, val_keys, val_pages, val_loc, args.debug, args.headless, args.skip_captcha, has_proxies, discovery_results=discovery_keywords, state=state, checkpoint_path=checkpoint_path)
                
                # Harvesting & ATC Verifier
                logging.info(" [Phase 2] Harvesting contact details...")
                await harvest_all_contacts(context, 5, state=state, checkpoint_path=checkpoint_path)
                
                logging.info(" [Phase 3] Verifying Ad Transparency registry...")
                # Reuse browser for ATC (enrich_all_atc can take context)
                await enrich_all_atc(context.browser, concurrency=2, state=state, checkpoint_path=checkpoint_path)
                
                await context.close()

                break # SERP Scrape successful, exit rotation loop
                
            except ProxyRotateException as e:
                logging.warning(f"Rotation Triggered: {e}")
                if context: await context.close()
                if current_proxy and current_proxy in proxy_pool:
                    proxy_pool.pop(0)
                    logging.info(f" [!] Discarded failing proxy. {len(proxy_pool)} proxies left in pool.")
                
                await asyncio.sleep(2) # Anti-blink pause
                continue # Next iteration will use new proxy at pool[0]

            except Exception as e:
                logging.error(f"Fatal error during SERP Scrape: {e}")
                if context: await context.close()
                if current_proxy and current_proxy in proxy_pool:
                    proxy_pool.pop(0)
                    logging.info(f" [!] Discarded erroring proxy. {len(proxy_pool)} proxies left in pool.")
                
                await asyncio.sleep(5) # Give user time to read terminal
                if not proxy_pool:
                    raise e # Actually crash if we have no rotation fallback
                continue # Try next proxy if available

        # Phase 2: Contact Harvesting
        cb_args = {}
        if proxy_pool:
            cb_args["proxy"] = {"server": proxy_pool[0]}
            
        browser = await p.chromium.launch(headless=args.headless, **cb_args)
        # Enrichment: Contact Info
        context_contacts = await browser.new_context(user_agent=random.choice(CONFIG["user_agents"]))
        await context_contacts.add_init_script(STEALTH_SCRIPTS)
        await harvest_all_contacts(context_contacts, args.concurrency, state=state, checkpoint_path=checkpoint_path)
        await context_contacts.close()
        
        # Enrichment: Ads Transparency
        await enrich_all_atc(browser, concurrency=2, state=state, checkpoint_path=checkpoint_path)
        
        await browser.close()

    # Final Phase: Output Generation
    state["run_meta"]["status"] = "completed"
    flush_checkpoint(state, checkpoint_path)
    export_csv(state, args.output, partial=False)
    
    # Cleanup Completed Checkpoint
    try:
        if checkpoint_path and os.path.exists(checkpoint_path):
            os.remove(checkpoint_path)
            logging.info(f"Run completed. Checkpoint {checkpoint_path} cleaned up.")
    except:
        pass

if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle_interrupt)
    asyncio.run(main())
