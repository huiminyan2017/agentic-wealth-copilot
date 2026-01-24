# Roadmap – Agentic Wealth Copilot

This document outlines the phased development plan for Agentic Wealth Copilot.  Each phase introduces new capabilities while maintaining the privacy‑first, explainable and agentic principles of the system.  Later phases build upon earlier ones.

## Phase 1: Core System (MVP)

- 📦 **Multi‑agent orchestration** – Set up the planner agent and memory agent so the system can decide what tasks to perform and remember past interactions.
- 🧠 **Planner agent** – Route user requests to the appropriate domain modules and maintain the high‑level state of the system.
- 🔧 **Tool calling** – Integrate a basic tool‑use interface so agents can call external APIs (e.g. market data) safely.
- 💾 **Memory** – Implement a simple vector or relational store to persist user preferences and past actions.
- 📜 **Logging** – Capture all agent decisions, tool calls and responses for later auditing.
- 🌐 **Web UI** – Build a minimal Streamlit interface that lets users interact with the agents through a browser.
- 🔒 **Privacy‑first data handling** – Ensure that raw documents (W‑2s, paystubs) live only in `data/raw/` and are never committed.

## Phase 2: Income & Tax Intelligence

- 🧾 **W‑2 parser** – Extract key fields (Boxes 1–6, state wages, withholding) from PDF W‑2 forms.
- 💵 **Paystub parser** – Extract gross pay, deductions, taxes, net pay and year‑to‑date totals from bi‑weekly or monthly paystubs.
- 📈 **Income trend analysis** – Visualize income growth, volatility and anomalies over multiple years.
- 🧾 **Tax explanation engine** – Describe each line item on a paystub or W‑2 and explain why taxable wages differ from gross wages.
- 🎓 **Personalized tax education** – Teach basic tax concepts (e.g. FICA vs income tax, pre‑tax vs post‑tax deductions) using the user’s own data (locally).

## Phase 3: Wealth & Net Worth Tracking

- 🗄️ **Asset registry** – Define a schema for all types of assets (cash, brokerage, retirement, property, debt) and record their values, cost basis and owners.
- 🏠 **Property tracking** – Track purchase price, current estimated value, mortgage balance, equity and cash flow for real estate.
- 💰 **Savings tracking** – Keep tabs on savings and checking accounts, including interest accrual.
- 📊 **Family net worth aggregation** – Combine all assets and liabilities to compute total net worth, liquid net worth and invested net worth.
- 📉 **Wealth trend analysis** – Measure year‑over‑year change, asset mix shifts and concentration risks.

## Phase 4: Investing & Trading

- 📑 **Portfolio manager** – Record holdings, cost basis, allocation and unrealized gains/losses for stocks, ETFs and other securities.
- 📈 **Rule‑based trading engine** – Define conditional strategies (e.g. sell 20 % of MSFT if price ≥ $450) and monitor markets for triggers.
- ⏱️ **Market monitoring** – Fetch real‑time prices, volatility metrics and relevant news.
- 🧠 **Strategy reasoning** – Critically evaluate whether a rule still makes sense given current volatility, risk and tax impact.
- 🎮 **Paper trading simulator** – Execute trades virtually to evaluate strategy performance without risking capital.

## Phase 5: Intelligence Layer

- 🔮 **Scenario planning** – Simulate long‑term financial plans based on income, savings rate, investment returns and life events.
- 🤖 **Behavioral modeling** – Learn the user’s risk tolerance, response to market swings and investment preferences over time.
- 🧬 **Strategy evolution** – Use reinforcement or evolutionary techniques to refine trading and allocation strategies.
- 📉 **Regime detection** – Detect market regimes (bull, bear, sideways) and adapt strategies accordingly.
- 📆 **Long‑horizon forecasting** – Project income, tax liability and net worth years into the future under various scenarios.

## Phase 6: Cloud Deployment (Optional)

- ☁️ **Azure deployment** – Package the backend and frontend for deployment on Azure App Service or Azure Container Apps.
- 🔐 **Authentication** – Add user accounts and secure access to personal data.
- 🔒 **Encrypted storage** – Use Azure SQL or Azure Database for Postgres with encryption at rest.
- 🌍 **Public demo mode** – Provide a redacted demo environment for recruiters or collaborators without revealing personal data.

---

> **Note:** The roadmap is meant to be a living document.  As the project evolves, tasks may be reprioritized or additional phases may be added.