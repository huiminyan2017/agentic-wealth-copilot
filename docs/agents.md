# Agents Overview

Agentic Wealth Copilot uses a multi‑agent architecture in which specialized agents collaborate under the supervision of a Planner.  This document summarizes the purpose and responsibilities of each agent.

## Planner Agent

The Planner Agent acts as the central coordinator.  It interprets user requests, consults the memory for context, decomposes tasks into subtasks and routes them to the appropriate domain agents.  It also maintains a decision trace so that the rationale behind every action is recorded and can be explained.

## Memory Agent

The Memory Agent stores long‑term information about the user’s preferences, past decisions, feedback and summarized interactions.  It uses a vector store for semantic retrieval and/or a relational database for structured records.  The Planner consults the Memory Agent to personalize responses and avoid redundant prompts.

## Income & Tax Agent

This agent is responsible for ingesting and analyzing income documents (W‑2s and paystubs).  It extracts structured data, computes trends and explains tax concepts.  It may also generate educational content by querying the Knowledge Agent.

## Wealth Agent

This agent tracks assets and liabilities, computes net worth figures and analyzes wealth trends.  It interfaces with the Memory Agent to store asset records and uses alerts to notify the Planner of concentration risks or liquidity issues.

## Investing & Trading Agent

This agent manages the portfolio, defines and monitors rule‑based trading strategies and performs simulations.  It communicates with market data APIs and provides plain‑language explanations for each action.

## Knowledge Agent (RAG)

The Knowledge Agent provides retrieval‑augmented generation (RAG) capabilities.  When a domain agent needs to explain a concept, the Knowledge Agent searches a curated corpus of financial documents (e.g. IRS publications, Investopedia articles, academic papers), retrieves relevant passages and generates a response with citations.

## Risk/Critic Agent

The Risk Agent acts as a skeptic.  It reviews outputs from other agents, checks for logical consistency and highlights potential risks, such as over‑concentration, high volatility or unrealistic assumptions.  The Planner may ask the Risk Agent to critique a plan before presenting it to the user.

## Privacy Agent

The Privacy Agent enforces the redaction rules defined in `PRIVACY.md`.  Before any data leaves the local environment or is saved to a publicly visible location (e.g. `data/samples/`), the Privacy Agent sanitizes identifiers, amounts and dates.  It also monitors data flows to ensure that no raw personal data is accidentally exposed.

---

Additional agents can be added as the system grows (e.g. a Behavioral Modeling Agent in the intelligence layer) by following the same interface patterns.