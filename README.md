# Agentic Wealth Copilot

Agentic Wealth Copilot is a lifelong, privacy‑preserving, multi‑agent AI system designed to help individuals and families understand, track and optimize their finances.

It combines:

* **Income & tax intelligence** – W‑2 and paystub parsing, income trends and plain‑language tax explanations.
* **Net worth & wealth tracking** – aggregate property, savings, stocks, retirement accounts and debt to compute liquid net worth, equity and trends.
* **Rule‑based investing & trading** – define conditional trades (e.g. sell MSFT if price hits a threshold), monitor markets and run paper‑trading simulations.
* **Long‑term planning & reasoning** – an agentic core that plans tasks, reasons with memory and produces explainable recommendations.
* **Financial knowledge retrieval** – a retrieval‑augmented engine that draws upon trusted sources (IRS docs, Investopedia, etc.) to teach you fundamentals.

This is **not** a chatbot.  It is an autonomous, modular, explainable financial copilot that can grow with you for years.

---

## Core Principles

1. **Privacy‑first** – All personal data stays local by default.  Sensitive documents are never committed to the repository.
2. **Explainable** – Every recommendation is accompanied by a plain‑English justification and references.
3. **Agentic** – Uses multi‑agent planning and memory rather than single‑turn LLM calls.
4. **Long‑lived** – Designed to evolve over decades by adding new modules without rewriting the core.
5. **Auditable** – Decisions, memory and reasoning are logged so you can replay and review what happened.

---

## Repository Overview

This repository is your single source of truth for the project.  It contains both the application code and the living documentation that guides development.

```
agentic-wealth-copilot/
│
├── README.md            ← High‑level overview and project vision (this file)
├── ROADMAP.md           ← Phase‑by‑phase development plan
├── ARCHITECTURE.md      ← System design and data flow diagrams
├── DECISIONS.md         ← Architectural decision records (ADR‑style)
├── BUILD_LOG.md         ← Chronological build log of progress
├── PRIVACY.md           ← Redaction rules and data handling policies
│
├── docs/                ← Living documentation for individual modules
│   ├── income_tax.md
│   ├── wealth_tracking.md
│   ├── investing_trading.md
│   ├── agents.md
│   └── data_schemas.md
│
├── data/
│   ├── raw/             ← **Never committed**; personal documents live here
│   ├── samples/         ← Redacted or synthetic sample documents for testing
│   └── schemas/         ← JSON/YAML schema definitions
│
├── backend/             ← FastAPI server and core agent implementation
├── frontend/            ← Streamlit application for the web UI
└── .gitignore           ← Ignore sensitive files and caches
```

See `ARCHITECTURE.md` for more detail on how these pieces fit together.

---

## Status

🚧 **Early design and scaffolding phase.**  The core modules, agents and UI skeletons are being defined.  Functionality will be added incrementally according to the roadmap.

---

## Disclaimer

This project is for educational, simulation and planning purposes only.  It does **not** execute real trades or provide professional financial, legal or tax advice.  Always consult a certified professional before making any financial decisions.