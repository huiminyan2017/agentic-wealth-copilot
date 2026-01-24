# Architecture

This document describes the high‑level architecture of the Agentic Wealth Copilot system.  It explains how the user interacts with the system, how agents are orchestrated and how data flows through the various layers.

## High‑Level View

```
        ┌───────────────────────┐
        │       Web UI         │   ← Streamlit front end
        └─────────┬─────────────┘
                  │ HTTP/WS
                  ▼
      ┌─────────────────────────────┐
      │  Orchestration Layer        │
      │  (Planner Agent & Memory)   │
      └─────────┬───────────────────┘
                │
                ▼
      ┌─────────────────────────────┐
      │        Domain Agents        │
      │  • Income & Tax Agent       │
      │  • Wealth Agent             │
      │  • Investing & Trading Agent│
      │  • Knowledge Agent (RAG)    │
      │  • Risk/Critic Agent        │
      │  • Privacy Agent            │
      └─────────┬───────────────────┘
                │
                ▼
      ┌─────────────────────────────┐
      │        Data & Tools         │
      │  • Document ingestion (PDF) │
      │  • Market data APIs         │
      │  • Vector database          │
      │  • Relational database      │
      │  • Simulation engines       │
      └─────────────────────────────┘
```

### UI Layer

The **UI Layer** is a Streamlit application that runs locally or in the cloud.  It allows the user to input requests (e.g. “show me my net worth trend” or “set an MSFT threshold trade”), upload documents (W‑2s, paystubs) and view analyses.  The UI communicates with the FastAPI backend via HTTP endpoints.

### Orchestration Layer

The **Orchestration Layer** contains the Planner Agent and the Memory Agent.

* The **Planner Agent** interprets user intent, breaks tasks into subtasks and determines which domain agent should execute each subtask.  It also decides the order of operations and maintains a decision trace for explainability.
* The **Memory Agent** stores long‑term user preferences, past decisions and summaries of previous interactions in a vector store or relational database.  It allows the system to adapt and personalize over time.

### Domain Agents

Each **Domain Agent** encapsulates expertise in a specific area:

* **Income & Tax Agent** – Parses W‑2s and paystubs, analyzes income trends and explains tax concepts.
* **Wealth Agent** – Tracks assets and liabilities, computes net worth and identifies concentration risks.
* **Investing & Trading Agent** – Manages the portfolio, defines rule‑based strategies and monitors markets.
* **Knowledge Agent (RAG)** – Retrieves relevant financial information from a curated corpus (IRS docs, Investopedia, etc.) to answer conceptual questions and cite sources.
* **Risk/Critic Agent** – Evaluates the robustness of strategies, challenges assumptions and highlights potential risks or biases.
* **Privacy Agent** – Enforces redaction and sanitization rules before data is exposed outside the local environment or committed to the repository.

Agents communicate via defined interfaces and share state through the orchestrator.  They may call external tools (e.g. API wrappers) through a tool‑use abstraction layer that enforces safe access.

### Data & Tools Layer

The **Data & Tools Layer** handles interaction with external resources and persists information:

* **Document ingestion** – Uses PDF parsing and optional OCR to extract structured data from W‑2s and paystubs stored in `data/raw/`.
* **Market data APIs** – Queries stock prices, macro indicators and news from services like Alpha Vantage, Yahoo Finance or FRED.
* **Vector database** – Stores embeddings for long‑term memory and retrieval‑augmented generation.
* **Relational database** – Persists structured records for assets, trades, transactions and user preferences.
* **Simulation engines** – Perform backtesting, Monte Carlo simulations and scenario analyses.

---

## Data Flow

1. **User request** – The user interacts with the Streamlit UI, which sends a request to the FastAPI backend.
2. **Planning** – The Planner Agent interprets the request, consults the Memory Agent and decides which domain agents to invoke.
3. **Execution** – The selected Domain Agents perform their tasks (e.g. parse a document, compute a trend, call a market API) and return results.
4. **Reasoning & explanation** – The Planner Agent aggregates the results, invokes the Risk/Critic Agent for a sanity check and asks the Knowledge Agent to provide any necessary explanations.
5. **Response** – The UI displays the structured data, charts and textual explanations to the user.  Decisions and outputs are logged for auditing.

---

## Privacy Model

Raw personal data such as W‑2 PDFs and paystubs are stored only in `data/raw/`, which is excluded from version control by `.gitignore`.  The Privacy Agent ensures that when data is used for public examples, it is sanitized according to the rules defined in `PRIVACY.md`.  Only redacted or synthetic samples are committed to `data/samples/` for testing and documentation.

The backend is designed to run locally by default.  When deployed to the cloud, it should be configured with encrypted storage, authentication and strict access controls.

---

## Future Enhancements

As the system matures, the architecture can be expanded to include:

* **Event‑driven workflows** – Use message queues to trigger asynchronous tasks like periodic market polling or scheduled simulations.
* **Machine learning models** – Incorporate predictive models for income forecasting, property valuation or risk scoring.
* **Third‑party integrations** – Connect to brokerage APIs for read‑only account data or to budgeting tools for automatic expense categorization.

These enhancements should be implemented in a modular fashion so they can be added without breaking existing functionality.