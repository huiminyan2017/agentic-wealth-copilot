# Agents — Architecture & Call Flow

The `agents/` folder is the AI reasoning layer between the FastAPI backend and Azure OpenAI.
It classifies what a user's question is about, runs the right analysis, and composes a reply.
All data parsing happens deterministically in the backend; agents only touch already-parsed JSON
stored in `data/parsed/<person>/`.

---

## File Structure

```
agents/
  llm.py               Lazy Azure OpenAI wrapper — all LLM calls go through here
  state.py             CopilotState dataclass threaded through every graph node
  graph.py             Wires nodes into a LangGraph, compiles once, exposes run_copilot()
  income_analysis.py   6-step deterministic pipeline — NO LLM, results are cached
  nodes/
    routing.py               Classify intent via LLM + keyword fallback
    general_questions.py     Open-ended personal finance Q&A — calls LLM
    income_tax.py            Synthesise answer from income report + user question — calls LLM
    wealth.py                Compute net worth table, then narrate via LLM
    investing.py             Stub — no LLM, returns placeholder text
    critic.py                Keyword safety check — no LLM, appends to trace only
```

---

## How a Query Flows Through the Graph

### Compile time vs runtime

`graph.py` calls `_build().compile()` **once at import time**, before any request arrives.
Compilation validates edges and builds a reusable executor. No nodes run until a request comes in.

### Per-query execution — always 3 nodes

Each `POST /api/copilot` call runs exactly **routing → one domain node → critic**:

```
POST /api/copilot  {message, session_id}
    │
    └─► run_copilot(message, session_id)          agents/graph.py
            │
            │  fresh CopilotState created per call (no shared mutable state between requests)
            │
            ▼
        routing_node                               agents/nodes/routing.py
            LLM chat_json() → {intent, people, sub_intent, confidence}
            if LLM unavailable → keyword fallback (w2/paystub → income_tax, etc.)
            sets state.intent, state.person, state.sub_intent
            │
            ▼  conditional edge on state.intent
            │
            ├─ "income_tax" ──► income_tax_node   agents/nodes/income_tax.py
            │                       run_income_analysis(person)        [NO LLM]
            │                           checks cache (person + file mtimes)
            │                           load → trends → anomalies → insights → actions → report
            │                       LLM: answer user's question using report as context
            │                       fallback: return Markdown report directly
            │
            ├─ "wealth" ─────► wealth_node         agents/nodes/wealth.py
            │                       load wealth.json for all people in data/parsed/
            │                       compute net worth + pairwise diffs    [NO LLM]
            │                       LLM: narrate the comparison table
            │                       fallback: return raw Markdown table
            │
            ├─ "investing" ──► investing_node       agents/nodes/investing.py
            │                       stub — returns placeholder message    [NO LLM]
            │
            └─ "general" ────► general_node         agents/nodes/general_questions.py
                                    LLM: answers open-ended financial question
                                    fallback: static help message listing supported domains
            │
            ▼  all paths converge
        critic_node                                agents/nodes/critic.py
            keyword scan: sell/buy/trade/order → append paper_only warning to trace
            does NOT modify state.reply             [NO LLM]
            │
            ▼
        return (state.reply, state.trace)  ──►  JSON response to frontend
```

### The conditional edge

After `routing_node` sets `state.intent`, LangGraph calls `_route(state)` which returns that
string and jumps directly to the matching node — a switch, not a fan-out. The three idle nodes
consume zero CPU for that query.

```python
g.add_conditional_edges(
    "routing", _route,
    {
        "income_tax": "income_tax",
        "wealth":     "wealth",
        "investing":  "investing",
        "general":    "general",
        "unknown":    "general",
    },
)
```

### Concurrency

Nodes run sequentially within a single request — the chain is linear. Two simultaneous HTTP
requests each get their own `CopilotState` and do not interfere with each other.

---

## Nodes

### routing  (`nodes/routing.py`)

**LLM:** `chat_json()` — temperature 0.1, max 500 tokens, JSON response mode.

Classifies intent and extracts context from the user message. Low temperature keeps routing
deterministic. If the LLM is unavailable, falls back to keyword matching without erroring —
the user still gets a useful response, and the trace records `routing:llm_unavailable:keyword_fallback`.

| Keywords in message | Intent routed to |
|---|---|
| w2, paystub, withholding, salary, tax, income | `income_tax` |
| net worth, wealth, property, mortgage, savings, asset, brokerage, compare | `wealth` |
| sell, buy, threshold, trading, rebalance | `investing` |
| everything else | `general` |

### income_tax  (`nodes/income_tax.py`)

**LLM:** `chat()` — temperature 0.2, max 1500 tokens.

1. Calls `run_income_analysis(person)` — fully deterministic, no LLM (see pipeline below).
2. Passes the resulting Markdown report + the user's question to the LLM.
3. LLM produces a focused, conversational answer drawn from the report.
4. If the LLM is unavailable, returns the raw Markdown report (still a complete, useful answer).

### wealth  (`nodes/wealth.py`)

**LLM:** `chat()` — temperature 0.2, max 1500 tokens.

Discovers all people with a `wealth.json` in `data/parsed/`. Computes for each:

```
net_worth = cash + primary_property + investment_properties + stock_value + retirement_401k
```

Renders a summary table and pairwise diffs. All arithmetic is deterministic. The LLM then
narrates the table in response to the user's specific question.

### general  (`nodes/general_questions.py`)

**LLM:** `chat()` — temperature 0.2, max 1500 tokens.

Open-ended financial Q&A with a financial advisor system prompt. No pre-computed data injected —
the LLM answers from general knowledge. If unavailable, returns a formatted help menu listing
the four domains the copilot supports.

### investing  (`nodes/investing.py`)

**No LLM.** Stub. The UI has a full investing page (watchlist, live quotes, charts, price alerts)
but the copilot agent node is not yet implemented. Returns a placeholder explaining the planned
rule-based trading feature.

### critic  (`nodes/critic.py`)

**No LLM.** Runs after every domain node. Scans the original user message for trading keywords
(`sell`, `buy`, `trade`, `order`). If found, appends `critic:trading_safety=paper_only` to the
trace. Never modifies `state.reply`.

---

## Income Analysis Pipeline  (`income_analysis.py`)

No LLM calls anywhere in this file. Every step is deterministic arithmetic or rule-based logic.
Results are cached by `(person, tuple(file-mtimes))` — re-uploading a document busts the cache
automatically.

### Step 1 — `load_income_data(person)`

Reads all `*.json` files from `data/parsed/<person>/paystub/` and `data/parsed/<person>/w2/`.
Returns a dict with `paystubs`, `w2s`, and a `summary` (counts, years covered, employer names).

### Step 2 — `compute_trends(paystubs, w2s)`

- **Monthly series** — per-month totals of gross, net, each tax component, pre/post-tax deductions, stock income, and effective tax rate.
- **Yearly summary** — same fields rolled up by year. If a W-2 exists, it overrides the paystub aggregation for that year (W-2 is the authoritative annual figure).
- **YoY income growth** — percentage and dollar change between consecutive years.

### Step 3 — `detect_anomalies(trends, paystubs, w2s)`

| Check | Threshold | Severity |
|---|---|---|
| Tax rate change YoY | >3% | medium; >5% → high |
| Income volatility | CV >15% across monthly gross | medium; CV >25% → high |
| SS wage cap hit | SS wages ≥ 95% of annual limit | info |
| Stock income pattern | Stock in <80% of months but ≥2 months | info |
| Deduction change MoM | >20% | low; >30% → medium |

SS wage limits are defined for 2018–2026 so historical demo data (2018) is handled correctly.

### Step 4 — `generate_insights(trends, anomalies, w2s)`

Converts numbers and anomalies into insight objects with `category` and `priority`:

- **tax_optimization** — effective rate >25%, significant rate change, SS cap reached, HSA under-contributed
- **income_stability** — income growth >10%, income decrease >5%, high volatility
- **retirement** — 401(k) contributions below 90% of the annual limit

### Step 5 — `propose_actions(insights, anomalies, trends)`

Maps insights to concrete dollar-amount actions:

- 401(k) gap → "increase by $X/year ($Y/paycheck bi-weekly), saves $Z in taxes"
- HSA gap → "increase by $X/year for triple tax advantage"
- High effective rate → "review W-4 withholding"
- Income >$200k → "consider tax planning consultation (backdoor Roth, ESPP, options)"

### Step 6 — `compile_report(...)`

Formats all of the above into a single Markdown document with emoji-coded severity indicators.
This report is what `income_tax_node` passes to the LLM as context.

### Cache

```python
key = (person, tuple(file_mtime for each parsed JSON))
```

- Same person, same files → cache hit, returned instantly (`trace` includes `cache:hit`)
- User uploads a new document → mtime changes → cache miss → pipeline re-runs
- Different person → different key → always a fresh run

---

## LLM Client  (`llm.py`)

Lazy-initialized wrapper around Azure OpenAI. The client is created on the first call and reused.
Returns `None` on any initialization or API error so every node can fall back gracefully.

```python
chat(messages, temperature=0.2, max_tokens=1500) -> str | None
chat_json(messages, temperature=0.1)             -> dict | None  # enforces JSON response format
config_error_reply()                             -> str          # user-facing setup error string
```

`chat_json()` uses `response_format={"type": "json_object"}` to guarantee valid JSON.
Used only by the routing node where a structured `{intent, people, sub_intent, confidence}`
response is required.

---

## Azure OpenAI Setup

### Step 1 — Create the resource

1. Go to **portal.azure.com** → search **"Azure OpenAI"** → **Create**
2. Fill in:
   - **Region**: East US, East US 2, or Sweden Central (reliable `gpt-4o-mini` quota)
   - **Pricing tier**: Standard S0
3. **Review + Create** → wait ~1 min

### Step 2 — Copy credentials

Open the resource → **Keys and Endpoint** → copy **Key 1** and the **Endpoint** URL.

### Step 3 — Deploy the model

**Azure OpenAI Studio** → **Deployments** → **Deploy base model** → select `gpt-4o-mini` → name it `gpt-4o-mini` → **Deploy**.

### Step 4 — Update `.env`

```
AZURE_OPENAI_ENDPOINT=https://<your-resource-name>.openai.azure.com/
AZURE_OPENAI_API_KEY=<Key 1>
AZURE_OPENAI_API_VERSION=2024-12-01-preview
AZURE_OPENAI_DEPLOYMENT=gpt-4o-mini
```

### Step 5 — Restart the backend

```bash
pkill -f uvicorn
.venv/bin/uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 &
```

Verify by asking the copilot a question — the trace should show `routing:llm:intent=...`
instead of `routing:llm_unavailable:keyword_fallback`.
