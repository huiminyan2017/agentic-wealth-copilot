# Privacy & Data Handling

Agentic Wealth Copilot is designed to protect sensitive personal information.  This document defines the principles and rules for storing, processing and sharing data within the project.

## Principles

1. **Local‑first** – Raw personal data such as W‑2s, paystubs, bank statements and other financial documents should reside only in the `data/raw/` directory on the user’s machine.  These files must never be committed to version control.
2. **Sanitize before sharing** – Any data that leaves the local environment (e.g. sample datasets committed to the repository or public demo outputs) must be sanitized.  Identifying information is removed or replaced with consistent fake tokens and numeric values are scaled or bucketed to preserve relationships without revealing exact amounts.
3. **Explain what you reveal** – Whenever a module exposes processed data to the user or external systems, it should clearly state what information is included and why.  There should be no hidden leaks of personally identifiable information (PII).
4. **User control** – The user must remain in control of which documents are ingested and how long they are retained.  Provide simple ways to delete or replace data.
5. **Compliance** – If the system is deployed to a cloud environment, configure encryption at rest, transport security, authentication and least‑privilege access controls in accordance with best practices.

## Data Categories

### Raw Data (Never Committed)

Stored in `data/raw/` and ignored by git:

- W‑2 forms and paystubs
- Bank and brokerage statements
- Real property documentation
- Any file containing personally identifiable information

### Shareable Data

Stored in `data/samples/` or `docs/` and committed to the repository:

- Synthetic or redacted examples of documents that mimic the structure of real W‑2s, paystubs or statements
- JSON/YAML schemas defining expected fields
- Aggregated statistics or charts without individual identifiers

### Runtime Data

Stored in local databases (SQLite, Postgres) or vector stores:

- Parsed and normalized records (e.g. `W2Record`, `PaystubRecord`, `Asset`)
- Embeddings for long‑term memory
- Logs of agent decisions and tool calls

Runtime data is persisted locally; if run in the cloud, it must be stored in encrypted databases.

## Redaction Rules

When creating synthetic or redacted datasets:

* **Identifiers** – Replace names, addresses, Social Security numbers, employer names and any unique identifiers with consistent fake tokens (e.g. `EMPLOYER_01`, `USER_01`).
* **Amounts** – Apply a per‑record multiplier or bucket amounts into ranges so that relative relationships remain consistent but absolute values are obscured.
* **Dates** – Shift dates by a constant offset (e.g. add 7 days) or by year to anonymize specific days while preserving sequence.
* **Notes** – Remove or replace any free‑text comments that might contain PII or sensitive context.

These rules should be enforced by a dedicated **Privacy Agent** that processes any data destined for public consumption or storage outside `data/raw/`.

## Usage Guidelines

* **Never commit raw data** – Verify that `data/raw/` is excluded by `.gitignore` and ensure that test scripts and notebooks do not inadvertently read from it when generating publicly visible output.
* **Reference sanitized samples** – When writing tests, documentation or examples, use the files in `data/samples/` rather than your own documents.  Generate these samples via the sanitization pipeline.
* **Review before sharing** – Before pushing commits or sharing results, review all generated files to confirm that no sensitive information has slipped through.

By adhering to these guidelines, you can safely develop and showcase the Agentic Wealth Copilot without compromising personal data.