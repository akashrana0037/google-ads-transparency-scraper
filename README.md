# 🛰️ Vyom (Vector-Eye) v2.0
### Autonomous Google Ads Sector Intelligence & Competitor Engine

Vyom (Vector-Eye) is a precision-engineered intelligence tool designed to map out entire commercial sectors by identifying active advertisers and harvesting their high-value metadata. Unlike generic scrapers, Vyom operates on **Sectors**, not just keywords, and strictly filters for **active ad-spend targets**.

---

## ⚡ Elite Performance Features

### 1. 🧠 Alphabet Soup Sector Discovery
Provide a single high-level sector (e.g., *"Luxury Real Estate"*), and the engine autonomously discovers the **Top 20 high-intent transactional keywords** using:
*   **Alphabet Expansion**: Iterating through `Sector + [a-z]` suggestions.
*   **Transactional Scoring**: Algorithms that prioritize keywords with "buying signals" (*Price, Best, Agency, Quote*).
*   **PAA mining**: Extracting "People Also Ask" questions and converting them into keyword targets.

### 2. 🛡️ Absolute Advertiser Filtering
Maximize your ROI by focusing only on competitors spending money.
*   **Verified Ads Only**: The system filters out organic noise.
*   **Multi-Source Validation**: Domains are cross-referenced with the **Google Ads Transparency Center (ATC)** to confirm active advertiser status and Ad IDs.

### 3. 🕴️ Stealth-First Architecture
Bypass Google's modern anti-bot measures:
*   **Human Simulation**: Mimics human typing and navigation behavior.
*   **Identity Shifting**: Rotates User-Agents, Viewports, and Hardware signatures.
*   **Persistent Trust**: Support for persistent Google login sessions to establish "Trusted Session" status.

### 4. 💎 Sky-Blue Command Center
A premium React Dashboard featuring:
*   **Intelligence Grid**: Real-time streaming lead data.
*   **Ghost Feed**: Live telemetry logs from the scraping engine.
*   **One-Click Export**: 120-minute atomic CSV reports with enriched advertiser metadata.

---

## 🛠️ Quick Installation

### 1. Requirements
*   Python 3.10+
*   Node.js & npm (for Frontend)
*   Playwright Browsers

### 2. Setup
```bash
# Install Python Dependencies
pip install -r requirements.txt
playwright install chromium

# Install Frontend Dependencies
cd frontend
npm install
```

### 3. Execution
**Start the Backend Engine:**
```bash
python main_api.py
```

**Start the Dashboard:**
```bash
cd frontend
npm run dev
```

Visit `http://localhost:3000` to launch your first mission.

---

## 📂 Architecture
*   `scraper.py`: The core autonomous intelligence engine.
*   `main_api.py`: FastAPI backend orchestrator & task manager.
*   `frontend/`: The high-fidelity React dashboard.
*   `output/`: Automated CSV and debug captures.

---

## ⚖️ License & Ethics
This tool is for competitive intelligence and research purposes. Users are responsible for adhering to Google's Terms of Service and local privacy regulations.
