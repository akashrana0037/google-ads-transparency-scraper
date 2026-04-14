# 🏹 Vyom: Vector-Eye Scraper Elite 🚀

**An autonomous, high-stealth competitor analysis and lead generation engine.**

Vyom (Vector-Eye) is a high-performance scraping system that captures Google Ads, Local, and Organic results, then crawls competitor websites for "contact intelligence" (emails, phones, social links). It now features a professional Web UI and a robust FastAPI backend.

---

## 🏗️ System Architecture

- **Frontend**: React + Vite + Tailwind CSS (Cyberpunk/Dark aesthetic)
- **Backend**: FastAPI (Python) with AsyncIO task orchestration
- **Engine**: Playwright (Stealth) + BeautifulSoup4
- **Reporting**: Automated CSV generation and atomic JSON checkpointing

---

## 🚀 Getting Started

### 1. Backend Setup (API & Scraper)
```bash
# Navigate to the scrapper directory
cd scrapper

# Install dependencies
pip install -r requirements.txt
# (Ensure playwright chromium is installed)
playwright install chromium

# Launch the API server
python main_api.py
```
*The API will be available at `http://localhost:8000`.*

### 2. Frontend Setup (Web UI)
```bash
# Navigate to the frontend directory
cd scrapper/frontend

# Install dependencies
npm install

# Launch the development server
npm run dev
```
*The UI will be available at `http://localhost:5173` (default Vite port).*

---

## 💻 CLI Mode (Standalone)

You can still run the scraper directly via command line for quick audits:

```bash
# Example: Scrape 4 pages for a keyword with 5 concurrent site visits
python scraper.py --keywords "best solar panels" --pages 4 --concurrency 5
```

### Advanced CLI Options:
- `--proxy-list "proxies.txt"`: Enable autonomous proxy rotation.
- `--resume "path/to/checkpoint.json"`: Resume an interrupted mission.
- `--headless False`: Watch the "Silent Hunter" in action (non-headless mode).

---

## 🛡️ Stealth & Resilience

- **JS Fingerprint Masking**: Removes `navigator.webdriver` flags and mocks hardware signatures.
- **Human Behavior Simulation**: Randomized mouse movements and non-linear scrolling.
- **Self-Healing Loop**: Automatically destroys and recreates browser contexts on CAPTCHA detection.
- **Atomic Checkpointing**: Zero data loss; flushes to disk after every page load.

---

## 📊 Output Specification

Results are saved to the `output/` directory in two formats:
1. **CSV Reports**: Professional spreadsheets for CRM import.
2. **JSON Checkpoints**: Full session state for resumption and API serving.

**Data captured includes**:
- Result Type (Ad/Local/Organic)
- Contact Info (Emails, Phones, Addresses)
- Social Metadata (LinkedIn, FB, Twitter/X, etc.)
- Scrape Status & Latency

---
*Built for elite intelligence gathering by Vyom Agents.*
