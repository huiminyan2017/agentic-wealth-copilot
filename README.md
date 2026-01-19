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

## Running Agentic Wealth Copilot Locally

This project requires Python 3.10+. macOS ships with Python 3.9, which is not compatible with modern typing and AI tooling.
### 1. Check Your Python Version
python3 --version
which python3
if you see:
Python 3.9.x
/usr/bin/python3
You must install a newer Python.

### 2. Install Latest Python (macOS)
If you don’t have Homebrew:
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
Then install Python:
    brew install python
Verify:
    python3 --version
    which python3 
    you should see:
        Python 3.11.x or 3.12.x
        /opt/homebrew/bin/python3

### 3. Create Virtual Environment
From the project root:
    cd agentic-wealth-copilot
    rm -rf .venv
    python3 -m venv .venv
    source .venv/bin/activate
Verify:
    python --version

### 4. Install Dependencies
pip install --upgrade pip
pip install -r requirements.txt

### 5. Start Backend (FastAPI)
chmod +x backend/run_dev.sh
./backend/run_dev.sh
Health check:
http://127.0.0.1:8000/health

### 6.Start Frontend (Streamlit UI)
Open a new terminal:
cd agentic-wealth-copilot
source .venv/bin/activate
streamlit run frontend/app.py
Open in browser:
http://localhost:8501


## Input File name convention in Incoming & text
To ensure accurate and reliable parsing, Agentic Wealth Copilot infers certain metadata (document type, employer, date/year) from file names. While we also extract information from the PDF content itself, following this naming convention greatly improves robustness, speed, and correctness—especially for batch ingestion.
Paystubs:
Format: <Employer>-Paystub-YYYY-MM-DD.pdf
Examples: Microsoft-Paystub-2026-01-15.pdf

W-2:
Format: <Employer>-W2-YYYY.pdf
Example: Microsoft-W2-2024.pdf


### DEBUG
Q:(.venv) huiminyan@huimins-MacBook-Pro agentic-wealth-copilot % ./backend/run_dev.sh
INFO:     Will watch for changes in these directories: ['/Users/huiminyan/Documents/agentic-wealth-copilot']
ERROR:    [Errno 48] Address already in use

lsof -i:8000
COMMAND   PID      USER   FD   TYPE             DEVICE SIZE/OFF NODE NAME
WeChat  15056 huiminyan  278u  IPv4 0xb38bdc966678b509      0t0  TCP 172.16.224.47:58617->49.51.190.94:http-alt (ESTABLISHED)
(.venv) huiminyan@huimins-MacBook-Pro agentic-wealth-copilot % kill -9 15056


## Disclaimer

This project is for educational, simulation and planning purposes only.  It does **not** execute real trades or provide professional financial, legal or tax advice.  Always consult a certified professional before making any financial decisions.