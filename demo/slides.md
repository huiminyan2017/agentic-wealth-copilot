# Agentic Wealth Copilot — Interview Slides
<!-- Formatted for Marp / Slidev / any "---" slide renderer -->
<!-- Screenshots referenced: demo/screenshots/XX_*.png -->

---

## Slide 1 — Title

# Agentic Wealth Copilot

**A privacy-first, agentic AI system for personal finance intelligence**

> "Not a chatbot. An autonomous, explainable copilot designed to grow with you over decades."

**Stack:** Python · FastAPI · LangGraph · Streamlit · Azure OpenAI · yfinance

---

## Slide 2 — The Problem

### Why does personal finance need agents?

|         Pain Point             |        Status Quo           |                     This Project                    |
|--------------------------------|-----------------------------|-----------------------------------------------------|
| Parsing pay documents          | Manual entry, error-prone   | Deterministic parser + arithmetic proof             |
| Understanding trends           | Spreadsheets                | 6-step deterministic income intelligence pipeline   |
| Investment tracking            | Fragmented apps             | Real-time watchlist with scheduled price alerts     |
| Asking "what if" questions     | Generic chatbots            | Domain-routed LangGraph agents                      |
| Household finances             | Per-person tools            | Multi-person wealth comparison                      |

---

## Slide 3 — What It Does

### Five integrated modules

```
┌────────────────────────────────────────────────────────────────────────┐
│   Income & Tax   │  Wealth   │  Investing  │  Spending  │ Copilot Chat │
│  parse W-2/stub  │ net worth │  watchlist  │  receipts  │ LangGraph    │
│  trend analysis  │ targets   │  alerts     │  analytics │  agentic     │
└────────────────────────────────────────────────────────────────────────┘
```

All modules: **local-first, privacy-preserving, LLM-optional**

_Screenshot: `01_income_document_ingestion.png`_

---

## Slide 4 — Architecture

```
┌──────────────────────────────────────────┐
│          Streamlit Frontend              │
│   5 pages + person selector              │
└──────────────────┬───────────────────────┘
                   │ HTTP / REST
                   ▼
┌──────────────────────────────────────────┐
│            FastAPI Backend               │
├──────────────────────────────────────────┤
│  /api/copilot ──► LangGraph Orchestrator │
│  /api/income  ──► PDF Parser + Trends    │
│  /api/stocks  ──► yfinance + Cache       │
│  /api/alerts  ──► APScheduler + Email    │
│  /api/spending ─► CRUD + Azure OCR       │
└──────────────────┬───────────────────────┘
                   │
                   ▼
        data/parsed/<Person>/*.json
        (local only, .gitignored)
```

---

## Slide 5 — Income & Tax Module

### Deterministic parsing — no AI, no hallucinations

1. **PDF text extraction** via `pdfplumber` + regex per employer format
2. **Arithmetic validation**: 4 invariants checked per paystub (net pay ±$1.00, tax/deduction sums ±$0.01)
3. **W-2 box extraction** with IRS SS wage-cap checks per year (2018–2026)

_Screenshots: `04_income_paystub_validation.png` · `05_parsed_json_schema.png` · `06_parsed_w2_schema.png`_

### Why not use LLM/OCR for parsing?

| Dimension     | Deterministic    | AI            |
|---------------|------------------|---------------|
| Correctness   | Invariant-proven | Probabilistic |
| Auditability  | Full trace       | Black box     |
| Cost          | Free             | Per-document  |
| Testability   | Easy unit tests  | Hard to pin   |

> **Rule:** LLM touches only the final synthesis layer, never raw extraction.

---

## Slide 6 — Income Intelligence Pipeline

### A 6-step deterministic Python pipeline

```
load_data → compute_trends → detect_anomalies
    → generate_insights → propose_actions → compile_report
```

Pure Python — no LLM involved. Called from **two places in the UI**:

- **Income & Tax page** — "Analyze My Income & Taxes" button triggers it directly via `POST /api/income/analyze`
- **Copilot chat** — asking an income question routes to `income_tax_node`, which calls the same pipeline and passes the report to the LLM for narration

**Result cache:** keyed on `(person, file-mtimes)` — re-uploading a document auto-busts the cache.

**What comes out:**
- Monthly income aggregates, YoY growth rate
- Tax rate trends, anomaly flags (SS wage-cap violations, income spikes)
- Prioritized action items: "Increase 401(k) contribution from 6% → 10% — saves ~$X in taxes"

_Screenshot: `08_income_ai_insights.png`_

---

## Slide 7 — Wealth & Planning

### Multi-person net worth, done right

```
Total Wealth  = Cash + Primary Property + Investment Properties + Stocks + 401(k)
Liquid Wealth = Cash + Stocks + Investment Properties  (excludes home + 401k)
```

**Shared property handled correctly:**
- Two people can co-own an asset at any ownership split
- Each person's `wealth.json` records the ownership fraction; net worth = `value × fraction`

**Copilot integration:**
> "What is my net worth compared to [other person]?"
→ routing node routes to `wealth_node` → loads both JSONs → returns comparison table

_Screenshots: `11_wealth_asset_form.png` · `12_wealth_summary.png`_

---

## Slide 8 — Investing & Trading

### Real-time watchlist with scheduled price alerts

**Watchlist:**
- Per-person, stored in `data/parsed/<person>/watchlist.json`
- Preset categories: Tech, Consumer, EV/AI, Finance, Index ETFs
- Live quotes: price, Δ%, day range, 52W range, market cap, P/E, div yield

**Candlestick charts:** Plotly OHLCV with volume, periods 1W – 5Y

**Price Alerts:**
- Alert rule: `{ticker, direction, threshold_pct, time_range, email}`
- APScheduler runs every 2 hours, gated to market hours (9:30–16:00 ET, Mon–Fri)
- 24-hour cooldown after trigger; graceful fallback if SMTP not configured

_Screenshots: `13_investing_watchlist.png` · `15_investing_index_education.png`_

---

## Slide 9 — Spending Module

### Smart ingestion with duplicate prevention

**Receipt parsing:**
```
Upload image/PDF → Azure Document Intelligence → line items preview
    → Human review → deterministic ID = hash(date, amount, merchant)
    → Idempotent save (duplicate blocked automatically)
```

**Recurring spending:**
- Supports daily / weekly / biweekly / monthly / quarterly / yearly
- Auto-normalizes to monthly total regardless of frequency

**Analytics:** category breakdown, merchant frequency, one-time vs. recurring trends

_Screenshots: `09_spending_transactions.png` · `10_spending_analytics.png`_

---

## Slide 10 — The Agent System (LangGraph)

### Main graph routing

```
User message
    │
    ▼
[routing_node]          ← LLM intent classification + keyword fallback
    │
    ├─ "income_tax"  → income_tax_node  → run_income_analysis() → LLM narrates
    ├─ "wealth"      → wealth_node      → compare net worth across people
    ├─ "investing"   → investing_node   → deterministic stub (UI complete)
    ├─ "general"     → general_node     → LLM (free-form Q&A)
    └─ "unknown"     → general_node     ↗
         │
         └─ all domain nodes ──► [critic_node] ──► END
                                  keyword safety check + trace annotation
```

**Design principles:**
- Structured routing, not free-form tool calling
- Deterministic pipeline for complex analysis (income = 6-step pure Python)
- Full keyword fallback when LLM unavailable — app works without credentials

_Screenshot: `16_copilot_chat.png`_

---

## Slide 11 — Key Design Decisions

### 1. Deterministic first, AI last
Parsing is rule-based with arithmetic proofs. LLM only touches the final prose layer — reasoning is earned, not hallucinated.

### 2. LLM-optional architecture
Every agent node has a deterministic fallback. The app runs fully without Azure OpenAI credentials.

### 3. Privacy-first local storage
All PDFs and parsed JSON stay under `data/` — `.gitignored`, never uploaded unless explicitly via Azure OCR.

### 4. Agentic over chatbot
LangGraph with routing → domain node → critic is more reliable and auditable than a single-turn prompt with all data in context.

### 5. Household-aware
Finance is rarely solo. Shared property ownership, multi-person comparison, and cross-person watchlists are first-class concepts.

---

## Slide 12 — Tech Stack

| Layer                     | Tools                                              |
|---------------------------|----------------------------------------------------|
| **Agent orchestration**   | LangGraph 0.2+, langchain-core                     |
| **LLM**                   | Azure OpenAI (`gpt-4o-mini`)                       |
| **Backend**               | FastAPI, Uvicorn, Pydantic v2                      |
| **Frontend**              | Streamlit, Plotly                                  |
| **PDF parsing**           | pdfplumber, pdf2image                              |
| **OCR**                   | Azure Document Intelligence                        |
| **Market data**           | yfinance (quotes: 60s cache · history: 5min cache) |
| **Scheduling**            | APScheduler (background, market-hours gated)       |
| **Email**                 | SMTP stdlib                                        |
| **Testing**               | pytest                                             |
| **PDF generation**        | reportlab (test data only)                         |

All Python, all open source except Azure services.

---

## Slide 13 — Demo Data

### `DemoMicrosoftEmployee` — synthetic 2018 Microsoft payroll

- 4 paystubs (2018): $5,000 gross/period — obviously fake by design
- 1 W-2 (2018): totals consistent with paystubs; all arithmetic checks pass
- All groundtruth JSONs include `_disclaimer: "synthetic test data"`

**Why 2018?** Old dates signal "not real" immediately; IRS SS wage base for 2018 = $128,400 exercises cap logic.

**Real-world validation:**
> In actual use the system has ingested **130+ paystubs across multiple employers** and **5+ years
> of W-2s** — same parser, same schema, same arithmetic checks. The demo uses synthetic data to
> keep sensitive numbers out of the repo.

_Screenshots `05_parsed_json_schema.png` and `06_parsed_w2_schema.png` (slide 5) show the unified
paystub and W-2 schemas that work identically across employers._

---

## Slide 14 — Notable Achievements

| Achievement                    | How                                                                          |
|--------------------------------|------------------------------------------------------------------------------|
| Zero-hallucination parsing     | Arithmetic invariants on every paystub; 130+ real paystubs + 5 yrs W-2s      |
| Household-aware net worth      | Ownership fraction per asset in wealth model                                 |
| Real-time alerts without infra | APScheduler + market-hours gate + 24h cooldown                               |
| Lightweight income pipeline    | 6-step pure Python, mtime-keyed result cache                                 |
| Graceful LLM degradation       | Deterministic fallback in every node                                         |
| Idempotent ingestion           | SHA-256 hash dedup on document parse                                         |
| Full audit trail               | Agent trace logged per conversation turn                                     |

---

## Slide 15 — What's Next

- **Investing agent node** — routing works; `investing_node` is a stub (rule-based trading logic not yet implemented)
- **Tax optimization agent** — W-4 withholding recommendations based on trend data
- **Multi-currency support** — currently USD only
- **Plaid integration** — auto-import transactions from bank accounts
- **Mobile-responsive UI** — Streamlit has limitations; potential React frontend

---

## Slide 16 — Summary

> **Agentic Wealth Copilot** is a production-grade personal finance intelligence system.

**What makes it different:**

1. **Trustworthy** — Deterministic parsing with arithmetic proofs before any AI layer
2. **Agentic** — Multi-step LangGraph workflows, not single-turn prompts
3. **Private** — Local-first storage, no cloud unless you opt in
4. **Explainable** — Every recommendation has a plain-English justification
5. **Household-aware** — Multi-person, shared assets, cross-person comparisons
6. **Resilient** — Fully functional without LLM credentials

_Built with: Python · FastAPI · LangGraph · Streamlit · Azure OpenAI_

---

## Appendix — File Structure

```
agentic-wealth-copilot/
├── backend/app/
│   ├── main.py              # FastAPI + APScheduler lifespan
│   ├── routes/              # income, spending, stocks, alerts, copilot
│   └── services/            # paystub_parser, w2_parser, stock_service, paths
├── agents/
│   ├── graph.py             # LangGraph orchestrator (compile-once, invoke-per-request)
│   ├── llm.py               # Azure OpenAI wrapper (lazy init, fallback-safe)
│   ├── state.py             # CopilotState dataclass
│   ├── income_analysis.py   # 6-step deterministic pipeline + mtime cache
│   └── nodes/               # routing, income_tax, wealth, investing,
│                            #   general_questions, critic
├── frontend/
│   ├── app.py               # Streamlit root
│   ├── state.py             # ensure_session() — centralised session state
│   └── pages/               # 1_Income, 2_Wealth, 3_Investing, 4_Spending, copilot
├── data/raw/<Person>/       # Original PDFs (.gitignored)
├── data/parsed/<Person>/    # Parsed JSON (.gitignored)
├── demo/screenshots/        # 16 screenshots (05-06 static, rest captured by Playwright)
└── docs/                    # agents.md, income_tax.md, and 6 other design docs
```
