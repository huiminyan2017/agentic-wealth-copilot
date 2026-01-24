# Agentic Wealth Copilot — Demo Guide

This folder contains everything needed to walk someone through the project without a live instance running.

---

## What This Project Is

A full-stack, privacy-first personal finance assistant that combines:
- **Deterministic document parsing** (W-2s, paystubs) with strict mathematical validation
- **Multi-agent AI orchestration** via LangGraph, routing natural language queries to domain specialists
- **Real-time investing tools** — live stock quotes, candlestick charts, and scheduled price alerts
- **Spending tracker** with receipt OCR and recurring expense modeling

All personal data stays local. No cloud storage. The LLM (Azure OpenAI) only ever sees already-parsed, already-redacted structured data.

---

## Architecture in One Diagram

```
User (browser)
    │ HTTP
    ▼
Streamlit Frontend  ──── 5 pages: Chat, Income & Tax, Wealth & Planning,
    │                             Investing & Trading, Spending
    │ HTTP / REST
    ▼
FastAPI Backend
    ├── /api/copilot  ──────────► LangGraph Agent Graph
    │                               planner → income_tax | wealth | investing | general
    │                                              ↓             ↓
    │                               income_intelligence    wealth comparison
    │                               sub-agent (6 steps)   (load wealth.json)
    │                                              ↓
    │                                           critic → END
    │
    ├── /api/income   ──────────► paystub_parser + w2_parser (pdfplumber + regex)
    ├── /api/stocks   ──────────► yfinance (TTL-cached, 60s quotes / 5min history)
    ├── /api/alerts   ──────────► alert_service + APScheduler (every 2h, market hours)
    └── /api/spending ──────────► CRUD + Azure Document Intelligence (receipt OCR)

data/
├── raw/<Person>/paystub/, w2/        ← original PDFs (not committed)
└── parsed/<Person>/                  ← structured JSON (not committed)
    ├── paystub/, w2/, wealth.json
    ├── watchlist.json, alerts.json
    └── spending/, recurring.json
```

---

## Screenshots Index

| File | What it shows |
|---|---|
| `chat_01_empty.png` | Chat page on load |
| `chat_02_reply.png` | Agent reply: net worth comparison table (Huimin vs Bao) |
| `income_01_page.png` | Income & Tax page with DemoMicrosoftEmployee selected |
| `income_02_scan.png` | Document Ingestion panel — file preview before parsing |
| `income_03_trends.png` | W-2 table, wages/taxes chart, paystub list with validation status, drill-down |
| `income_04_analysis_summary.png` | Analysis: data summary + key metrics by year |
| `income_05_analysis_actions.png` | Analysis: findings, insights, recommended actions |
| `wealth_01_form.png` | Wealth form — balances filled in for Huimin |
| `wealth_02_full.png` | Wealth page full-length including summary metrics and targets |
| `investing_01_watchlist.png` | Watchlist cards with live prices (MSFT ▼, COST ▲) |
| `investing_02_chart.png` | Full page — watchlist + MSFT 1Y candlestick chart + stats |
| `investing_03_alerts.png` | Candlestick chart + ⚡ Price Alerts panel with configured rule |
| `spending_01_page.png` | Spending page — one-time transactions + receipt upload |
| `spending_02_full.png` | Spending page full-length |

---

## Demo Script

---

### 1. Copilot Chat

**Screenshot:** `screenshots/chat_02_reply.png`

![Chat reply](screenshots/chat_02_reply.png)

**What to show:**
- User types: *"What is my net worth compared to Bao?"*
- The planner agent classifies intent as `wealth`, loads `wealth.json` for both people
- Returns a structured comparison table: Huimin $1,095,000 vs Bao $600,000
- Shows per-component breakdown and pairwise differences

**Talking points:**
- Natural language entry point — no forms, no navigation required
- The agent graph routes to the right domain node automatically (LLM + keyword fallback)
- Response is grounded in real structured data, not hallucinated
- All agent reasoning steps are logged in the trace (visible in developer view)

---

### 2. Income & Tax — Page & Document Ingestion

**Screenshot:** `screenshots/income_01_page.png`

![Income page](screenshots/income_01_page.png)

**What to show:**
- Person selector (DemoMicrosoftEmployee selected — synthetic 2018 Microsoft data, obviously fake)
- Two primary actions: **Load Trends Now** and **Analyze My Income & Taxes**
- **Document Ingestion** expander for scanning and parsing raw PDFs

---

### 2b. Income & Tax — Document Scan

**Screenshot:** `screenshots/income_02_scan.png`

![Document scan](screenshots/income_02_scan.png)

**What to show:**
- "Scan raw folders" detects files in `data/raw/DemoMicrosoftEmployee/paystub/` and `data/raw/DemoMicrosoftEmployee/w2/`
- Filter by file type (w2, paystub) and year (2018)
- Preview table lists each file with type, employer, year, and path before ingestion
- User selects files then clicks Ingest — system deduplicates by SHA-256 hash

**Talking points:**
- Scan is non-destructive — preview only, nothing parsed until confirmed
- SHA-256 dedup means re-uploading the same PDF never creates duplicates
- Employer auto-detected from filename: `Microsoft-Paystub-2018-04-15.pdf → microsoft`

---

### 2c. Income & Tax — Trends: W-2 Summary, Charts & Paystub Validation

**Screenshot:** `screenshots/income_03_trends.png`

![Income trends](screenshots/income_03_trends.png)

**What to show:**
- **W-2 Annual Summaries** table: year 2018, wages $862,450, federal tax $318,782, SS tax $7,960.80 (capped at $128,400 SS wages), Medicare tax $21,828.15
- **W-2 Annual Wages & Taxes** bar chart — gross vs. tax breakdown visualized
- **Individual Paystubs** panel: 4 paystubs, 4/4 validation checks pass, 100% check pass rate
- Validation checks explained (expandable) — the algebraic invariant logic
- **Paystub Summary (High-Level)** table: all 4 rows with employer, year, gross, net, taxes
- **Paystub Details (Drill-Down)**: one paystub expanded showing:
  - Gross Income: $40,000 (Base $39,950 + Perks $50)
  - Pre-Tax Deductions: $1,374.99
  - Taxes: $17,072.00 (Federal, Medicare, State broken out)
  - After-Tax Deductions: $6,118.54 (ESPP + 401k-Roth)

**Talking points:**
- Every paystub passes a strict mathematical invariant: `gross − net − pretax − taxes − aftertax ≈ 0` (tolerance ±$0.02)
- SS wages capped at $128,400 for 2018 — the parser tracks this correctly across periods
- $40k/period is intentionally high to make the demo data obviously synthetic

---

### 2d. Income & Tax — AI Analysis Summary

**Screenshot:** `screenshots/income_04_analysis_summary.png`

![Analysis summary](screenshots/income_04_analysis_summary.png)

**What to show:**
- **Income Intelligence Analysis** section appears after clicking "Analyze My Income & Taxes"
- **Data Summary**: 4 paystubs analyzed, 1 W-2 analyzed, years covered 2018 & 2024, employer: microsoft
- **Key Metrics by Year**:
  - 2024: Gross $20,388, Effective Tax Rate 25.8%, Federal $3,002, State $702
  - 2018: Gross $862,450, Effective Tax Rate 45.8%, Federal $316,782, State $46,341

---

### 2e. Income & Tax — AI Insights & Recommended Actions

**Screenshot:** `screenshots/income_05_analysis_actions.png`

![Analysis actions](screenshots/income_05_analysis_actions.png)

**What to show:**
- **Findings** (anomalies detected):
  - Tax Rate Change: effective rate dropped from 45.8% → 25.8%
  - Income Volatility: high volatility detected across months
  - Block Income Pattern: gross income appears in 2-month blocks
  - Deduction Change: After-Tax Deductions decreased by 40% in 2024
- **Insights**: High Effective Tax Rate (flag), Significant Tax Rate Change, Income Volatility Detected
- **Recommended Actions** (prioritized, with impact estimates):
  1. Review Tax Withholding — large refund or underpayment risk
  2. Increase 401(k) Contribution — potential savings $720+/year at 25% marginal rate
  3. Verify Deduction Change in 2024-04 — may indicate benefits enrollment change
- Execution trace at bottom showing 6-step agent workflow

**Talking points:**
- All computation (trends, anomaly thresholds, action formulas) is deterministic — no LLM involved
- LLM is used only for the final synthesis layer: turning structured data into readable prose
- The 6-step sub-agent runs as an independent LangGraph graph — fully testable in isolation
- If Azure OpenAI is not configured, the raw Markdown report is returned directly (graceful fallback)

---

### 3. Wealth & Planning

**Screenshot:** `screenshots/wealth_01_form.png`

![Wealth form](screenshots/wealth_01_form.png)

**What to show:**
- Fields: Cash, Primary Property (with ownership split), Investment Properties, Stocks, 401(k)
- Ownership split logic: $1.2M property shared with 2 owners → $600K each
- Summary metrics auto-calculated at the bottom
- Savings targets with progress tracking
- Data persisted to `data/parsed/<person>/wealth.json`

**Talking points:**
- Household-aware: Huimin and Bao both own 50% of the same $1.2M property — each records their share
- The copilot can compare net worth across all people with data in a single query
- Targets are configurable per person — 401(k) target, non-retirement savings target

---

### 4. Investing & Trading — Watchlist & Quotes

**Screenshot:** `screenshots/investing_01_watchlist.png`

![Investing watchlist](screenshots/investing_01_watchlist.png)

**What to show:**
- Per-person stock watchlist (MSFT ▼ 1.59%, COST ▲ 0.62% — live prices)
- Add from preset categories (Tech, Consumer, EV/AI, Finance, Index) or custom ticker
- Real prices fetched via yfinance, cached 60 seconds
- Watchlist persisted in `data/parsed/<person>/watchlist.json`

**Talking points:**
- Session state pattern — add/remove updates are instant with no UI flicker
- Color-coded deltas (green = up, red = down) with directional arrows

---

### 4b. Investing & Trading — Price Chart

**Screenshot:** `screenshots/investing_02_chart.png`

![Investing chart](screenshots/investing_02_chart.png)

**What to show:**
- MSFT 1Y candlestick chart with volume bars below — live yfinance data
- Stats row: price, day range, 52W range, market cap ($2.94T), P/E, dividend yield
- Period selector: 1W / 1M / 3M / 6M / 1Y / 2Y / 5Y

---

### 4c. Investing & Trading — Price Alerts

**Screenshot:** `screenshots/investing_03_alerts.png`

![Investing alerts](screenshots/investing_03_alerts.png)

**What to show:**
- ⚡ Price Alerts panel with configured MSFT alert: direction both (▲▼), threshold 3%, period 1 day
- Recipient email shown, toggle on/off, delete button
- "Add New Alert" form below

**Talking points:**
- Alerts evaluated by APScheduler every 2 hours, gated to US market hours (9:30–16:00 ET, Mon–Fri)
- 24-hour cooldown prevents email spam when a condition stays met across multiple runs
- Email configured via `.env` SMTP settings (supports Gmail, Outlook/Hotmail, etc.)
- Backend also exposes `POST /api/alerts/{person}/check` for manual trigger / testing

---

### 5. Spending

**Screenshot:** `screenshots/spending_01_page.png`

![Spending](screenshots/spending_01_page.png)

**What to show:**
- Individual tab: One-Time Spending (date range filter, add form), Recurring Spending, Analytics
- Household Overview tab: aggregate across all people
- Receipt upload: drag-and-drop image → Azure Document Intelligence extracts line items → review → save
- Duplicate detection: system flags records with same date, amount, similar merchant

**Talking points:**
- Deterministic ID generation (hash of date + amount + merchant) means uploading the same receipt twice never creates a duplicate
- Recurring entries auto-calculate monthly total regardless of frequency (daily/weekly/monthly/quarterly/yearly)
- Receipt parsing returns items for human review before saving — no silent auto-save

---

## Key Technical Points to Highlight

| Topic | Detail |
|---|---|
| **Privacy model** | All data local. SSN/EIN redacted before any text reaches the LLM. Demo data uses synthetic 2018 figures. |
| **Parse reliability** | Every paystub parse validates a 4-field algebraic invariant. Invalid parses are flagged, not silently accepted. |
| **Agent design** | Planner uses LLM for intent classification with keyword fallback — works without API keys. |
| **LLM is optional** | Every agent node has a deterministic fallback. The app is fully functional without Azure OpenAI credentials. |
| **Scheduler** | APScheduler runs inside FastAPI via lifespan. Stock alerts fire every 2 hours, only during market hours. |
| **Extensibility** | New employer parsers, new agent nodes, new data sources plug in without touching existing code. |

---

## Refreshing Screenshots

If the app is running and data has changed:

```bash
# Both servers must be running first
.venv/bin/python scripts/take_screenshots.py
```

Requires playwright + chromium:

```bash
.venv/bin/pip install playwright
.venv/bin/playwright install chromium
```

---

## Running for a Live Demo

```bash
# Terminal 1 — backend
source .venv/bin/activate
./backend/run_dev.sh

# Terminal 2 — frontend
source .venv/bin/activate
streamlit run frontend/app.py
```

Open **http://localhost:8501**

Demo person with data: **Huimin** (wealth, watchlist, alerts), **Bao** (wealth — good for copilot comparison), **DemoMicrosoftEmployee** (income — synthetic 2018 Microsoft paystubs + W-2).
