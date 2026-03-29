# Agentic Wealth Copilot

A privacy-first, agentic AI system for personal finance intelligence — income analysis, wealth tracking, investing, and spending, unified under a natural-language copilot.

> Not a chatbot. An autonomous, explainable copilot built on LangGraph + FastAPI + Streamlit.

---

## Modules

| Module | Description |
|--------|-------------|
| **Income & Tax** | Parse W-2/paystub PDFs, arithmetic validation, trend analysis, LLM-driven Q&A |
| **Wealth & Planning** | Net worth across cash, property, stocks, retirement; fractional co-ownership; targets |
| **Investing & Trading** | Per-person watchlist, live quotes, Plotly candlestick charts, scheduled price alerts |
| **Spending** | One-time and recurring expenses, receipt OCR via Azure Document Intelligence |
| **Copilot Chat** | Natural language interface over all modules, routed by a LangGraph agent graph |

All modules are **local-first, LLM-optional** — the app runs fully without Azure OpenAI credentials.

---

## Architecture

```
Streamlit frontend  ──HTTP──►  FastAPI backend  ──►  data/parsed/<Person>/*.json
                                     │
                               LangGraph agents
                         routing → domain node → critic
```

- **Parsing** is fully deterministic (regex + arithmetic invariants) — validated on 130+ real paystubs and 5+ years of W-2s. See [docs/income_tax.md](docs/income_tax.md).
- **Agent routing** classifies intent via LLM with keyword fallback. See [docs/agents.md](docs/agents.md).
- **Income analysis** is a 6-step pure Python pipeline (no LLM) with mtime-keyed result cache.
- **All personal data** stays under `data/` — `.gitignored`, never committed.

---

## Quick Start

**Requirements:** Python 3.10+, poppler (`brew install poppler` on macOS)

```bash
# 1. Set up environment
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure
cp .env-example .env
# Edit .env — set AZURE_OPENAI_* for LLM features (optional)

# 3. Start backend  (terminal 1)
./backend/run_dev.sh

# 4. Start frontend  (terminal 2)
source .venv/bin/activate
streamlit run frontend/app.py
```

Open **http://localhost:8501** · Health check: `curl http://127.0.0.1:8000/health`

---

## Configuration

| Variable group | Required for |
|----------------|-------------|
| `AZURE_OPENAI_*` | LLM responses in copilot, insights, analysis narration |
| `SMTP_*` | Stock price alert emails |
| `AZURE_DOC_INTELLIGENCE_*` | Receipt OCR in Spending module |

Without Azure OpenAI, every agent node falls back to deterministic output automatically.
See [docs/agents.md — Azure OpenAI Setup](docs/agents.md#azure-openai-setup) for step-by-step instructions.

---

## Usage

### Income & Tax
1. Place PDFs in `data/raw/<Person>/paystub/` or `.../w2/` using the naming convention:
   `<Employer>-Paystub-YYYY-MM-DD.pdf` / `<Employer>-W2-YYYY.pdf`
2. **Scan → Ingest** on the Income & Tax page to parse them
3. View trends or click **Analyze My Income & Taxes** for AI-generated insights and actions

### Wealth & Planning
- Enter balances for cash, property, stocks, retirement; set savings targets
- Copilot: *"What is my net worth?"* or *"Compare net worth across people"*

### Investing & Trading
- Add tickers to your watchlist; view live quotes and candlestick charts
- Set price alerts with direction, threshold %, and email — fires during market hours only

### Spending
- Log one-time or recurring transactions; upload a receipt image for OCR parsing
- View category breakdowns and monthly trends

### Copilot Chat
Ask anything in natural language — *"What are my tax optimization opportunities?"*, *"How did my income change year over year?"*, *"What's my liquid net worth?"*

---

## Repository Structure

```
agentic-wealth-copilot/
├── backend/app/
│   ├── main.py              # FastAPI + APScheduler lifespan
│   ├── routes/              # income, spending, stocks, alerts, copilot
│   └── services/            # paystub_parser, w2_parser, stock_service, alert_service
├── agents/
│   ├── graph.py             # LangGraph graph (compile-once, invoke-per-request)
│   ├── llm.py               # Azure OpenAI wrapper (lazy init, fallback-safe)
│   ├── state.py             # CopilotState dataclass
│   ├── income_analysis.py   # 6-step deterministic pipeline + mtime cache
│   └── nodes/               # routing, income_tax, wealth, investing, general_questions, critic
├── frontend/
│   ├── app.py               # Streamlit root (Copilot Chat)
│   ├── state.py             # ensure_session() — centralised session state
│   └── pages/               # 1_Income_&_Tax, 2_Wealth_&_Planning, 3_Investing_&_Trading, 4_Spending
├── scripts/
│   ├── generate_demo_user_paystub_w2.py   # Regenerate synthetic demo PDFs + groundtruth
│   ├── income_ingest_tool.py              # CLI bulk ingestion
│   ├── income_groundtruth_tool.py         # CLI groundtruth check / save
│   └── generate_json_schema_screenshot.py # Regenerate demo/screenshots/05-06
├── tests/                   # pytest — paystub + W-2 ingest & parse, income trends/scan
├── data/raw/<Person>/       # Original PDFs (.gitignored)
├── data/parsed/<Person>/    # Parsed JSON (.gitignored)
├── demo/                    # Screenshots + slide deck
├── docs/                    # Design and API docs (see below)
├── requirements.txt
└── .env-example
```

---

## Testing

```bash
# Full suite
.venv/bin/python -m pytest tests/ -v

# Income parser only
.venv/bin/python -m pytest "tests/test_paystub_ingest_&_parse.py" "tests/test_w2_ingest_&_parse.py" -v

# Regenerate demo data then confirm tests pass
.venv/bin/python scripts/generate_demo_user_paystub_w2.py
.venv/bin/python -m pytest "tests/test_paystub_ingest_&_parse.py" "tests/test_w2_ingest_&_parse.py" -v
```

---

## Documentation

| Doc | Contents |
|-----|----------|
| [docs/agents.md](docs/agents.md) | Agent graph, node details, LLM call specs, Azure OpenAI setup |
| [docs/income_tax.md](docs/income_tax.md) | Schemas, validation invariants, pipeline steps, CLI tools |
| [docs/wealth_tracking.md](docs/wealth_tracking.md) | Wealth data model and fractional ownership logic |
| [docs/investing_trading.md](docs/investing_trading.md) | Watchlist, live quotes, candlestick charts |
| [docs/stock_alerts.md](docs/stock_alerts.md) | Alert rules, APScheduler, email, market-hours gate |
| [docs/spending.md](docs/spending.md) | Spending CRUD, receipt OCR, deduplication |
| [docs/design-on-doc-parsing.md](docs/design-on-doc-parsing.md) | Why deterministic parsing over AI/OCR |
| [docs/decisions-on-tradeoffs.md](docs/decisions-on-tradeoffs.md) | Architectural decision records |

---

## Disclaimer

For educational and personal planning purposes only. Does not execute real trades or provide professional financial, legal, or tax advice. Consult a certified professional before making financial decisions.
