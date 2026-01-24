# Agentic Wealth Copilot

A lifelong, privacy-preserving, multi-agent AI system designed to help individuals and families understand, track, and optimize their finances.

This is **not** a chatbot. It is an autonomous, modular, explainable financial copilot built on LangGraph + FastAPI + Streamlit.

---

## Core Principles

1. **Privacy-first** — All personal data stays local; sensitive documents are never committed to version control
2. **Explainable** — Every recommendation has plain-English justification
3. **Agentic** — Multi-agent planning and memory, not single-turn LLM calls
4. **Long-lived** — Designed to evolve over decades with a modular architecture
5. **Auditable** — Decisions, reasoning, and traces are logged for replay and review

---

## What It Can Do Today

| Module | Status | Description |
|---|---|---|
| Income & Tax | ✅ | Parse W-2/paystub PDFs, compute trends, detect anomalies, LLM-driven Q&A |
| Wealth & Planning | ✅ | Track net worth across cash, property, stocks, retirement; set targets |
| Investing & Trading | ✅ | Stock watchlist, real-time quotes, candlestick charts, price alerts + email |
| Spending | ✅ | Log one-time and recurring expenses, parse receipts via Azure OCR |
| Copilot Chat | ✅ | Natural language interface over all modules, routed by LangGraph agents |

---

## Repository Structure

```
agentic-wealth-copilot/
│
├── backend/                  # FastAPI server
│   └── app/
│       ├── main.py           # App factory, lifespan (starts scheduler)
│       ├── settings.py       # Pydantic settings (env vars)
│       ├── schemas.py        # Pydantic data models
│       ├── routes/           # API endpoints (income, spending, stocks, alerts, copilot)
│       └── services/         # Business logic (parsers, stock service, alert service, scheduler)
│
├── agents/                   # LangGraph multi-agent orchestration
│   ├── graph.py              # Main graph: planner → domain node → critic → END
│   ├── state.py              # CopilotState dataclass
│   ├── llm.py                # Azure OpenAI client (lazy init, graceful fallback)
│   ├── nodes/                # planner, income_tax, wealth, investing, general, critic
│   ├── subagents/            # income_intelligence (6-step analysis sub-graph)
│   └── tools/                # income_tools (load, trend, anomaly, insight, action)
│
├── frontend/                 # Streamlit UI
│   ├── app.py                # Chat interface (main page)
│   ├── api.py                # HTTP client wrapper for backend
│   ├── state.py              # Session state helpers
│   └── pages/
│       ├── 1_Income_&_Tax.py
│       ├── 2_Wealth_&_Planning.py
│       ├── 3_Investing_&_Trading.py
│       └── 4_Spending.py
│
├── docs/                     # Module-specific documentation
│   ├── agents.md             # Agent status and capabilities
│   ├── langgraph_architecture.md
│   ├── income_tax.md         # Schemas, validation, CLI tools
│   ├── design-on-doc-parsing.md
│   ├── wealth_tracking.md
│   ├── investing_trading.md  # Watchlist, quotes, alerts, scheduler
│   ├── spending.md           # Spending CRUD and receipt parsing
│   ├── stock_alerts.md       # Price alert rules, email, scheduling
│   └── decisions-on-tradeoffs.md
│
├── scripts/                  # CLI utilities
│   ├── generate_test_paystubs.py
│   ├── generate_test_w2.py
│   ├── income_ingest_tool.py
│   └── income_groundtruth_tool.py
│
├── tests/                    # pytest test suite
├── data/
│   ├── raw/<Person>/         # Original PDFs (not committed)
│   └── parsed/<Person>/      # Extracted JSON (not committed)
│
├── requirements.txt
├── .env-example              # Configuration template
└── CLAUDE.md                 # Development rules for AI assistants
```

---

## Quick Start

**Requirements:** Python 3.10+, poppler

```bash
# macOS
brew install python poppler

# 1. Create virtual environment
cd agentic-wealth-copilot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure environment
cp .env-example .env
# Edit .env — at minimum set AZURE_OPENAI_* if you want LLM features

# 3. Start backend
./backend/run_dev.sh
# or: python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload

# 4. Start frontend (new terminal)
source .venv/bin/activate
streamlit run frontend/app.py
```

Open **http://localhost:8501**

Health check: `curl http://127.0.0.1:8000/health`

---

## Using the App

### Income & Tax
1. Go to the **Income & Tax** page
2. Select or create a person
3. Place PDFs in `data/raw/<Person>/paystub/` or `data/raw/<Person>/w2/` using the naming convention:
   - `<Employer>-Paystub-YYYY-MM-DD.pdf`
   - `<Employer>-W2-YYYY.pdf`
4. Click **Scan** to detect documents, then **Ingest** to parse them
5. View trends and run AI analysis

### Wealth & Planning
1. Go to the **Wealth & Planning** page
2. Enter current balances for cash, property, stocks, retirement
3. Set savings targets
4. Use the **Copilot** chat to compare net worth across people

### Investing & Trading
1. Go to the **Investing & Trading** page
2. Add stocks to your watchlist (presets or custom tickers)
3. View real-time quotes and candlestick charts
4. Set price alerts: pick a stock, direction (up/down/both), threshold %, time range, and email
5. Configure SMTP in `.env` to receive email notifications

### Spending
1. Go to the **Spending** page
2. Log one-time transactions manually or upload a receipt image
3. Add recurring expenses with frequency
4. View category breakdowns and detect duplicates

### Copilot Chat
- Ask anything in natural language: *"How did my income change this year?"*, *"Compare my net worth with Bao"*, *"What's my effective tax rate?"*
- The planner agent routes to the right domain node, which runs analysis and generates an LLM-synthesized reply

---

## Configuration

Copy `.env-example` to `.env` and fill in values. Key sections:

| Section | Required for |
|---|---|
| `AZURE_OPENAI_*` | LLM-powered responses (copilot, insights, analysis) |
| `SMTP_*` | Stock price alert emails |
| `AZURE_DOC_INTELLIGENCE_*` | Receipt OCR parsing |

All features degrade gracefully — without Azure OpenAI, agents fall back to deterministic data output.

---

## Testing

```bash
# All tests
python -m pytest tests/ -v

# Specific modules
python -m pytest tests/test_paystub_parser.py -v
python -m pytest tests/test_w2_parser.py -v
```

Generate demo data for testing:
```bash
python scripts/generate_test_paystubs.py
python scripts/generate_test_w2.py
```

---

## Documentation

| Doc | Contents |
|---|---|
| [docs/agents.md](docs/agents.md) | Agent status, capabilities, graph topology |
| [docs/langgraph_architecture.md](docs/langgraph_architecture.md) | Detailed call flow diagrams |
| [docs/income_tax.md](docs/income_tax.md) | Schemas, validation invariants, CLI tools |
| [docs/design-on-doc-parsing.md](docs/design-on-doc-parsing.md) | Why deterministic parsing over AI OCR |
| [docs/wealth_tracking.md](docs/wealth_tracking.md) | Wealth data model and ownership logic |
| [docs/investing_trading.md](docs/investing_trading.md) | Watchlist, quotes, alerts |
| [docs/spending.md](docs/spending.md) | Spending CRUD and receipt parsing |
| [docs/stock_alerts.md](docs/stock_alerts.md) | Alert rules, email, scheduler |
| [docs/decisions-on-tradeoffs.md](docs/decisions-on-tradeoffs.md) | Architectural decision records |
| [docs/azure_openai_setup.md](docs/azure_openai_setup.md) | How to create/recreate the Azure OpenAI resource |

---

## Disclaimer

This project is for educational, simulation, and personal planning purposes only. It does **not** execute real trades or provide professional financial, legal, or tax advice. Always consult a certified professional before making financial decisions.
