# Income & Tax Module

The Income & Tax Module handles everything related to your income statements and tax obligations.  It provides structure for ingesting documents, analyzing trends and explaining tax concepts in plain language.

## Goals

* Parse W‑2 forms to extract wages, withholdings and other relevant boxes.
* Parse paystubs to extract gross pay, deductions, net pay and year‑to‑date totals.
* Produce year‑over‑year income trends and highlight anomalies (e.g. bonuses, salary raises, job changes).
* Explain why taxable wages differ from gross wages and what each deduction line means.
* Teach basic tax principles using the user’s own data (e.g. FICA vs income tax, pre‑tax vs post‑tax deductions).

## Planned Components

| Component          | Description |
|--------------------|-------------|
| **W2Parser**       | Module responsible for extracting structured fields from PDF W‑2 documents.  Handles OCR fallback when necessary. |
| **PaystubParser**  | Module responsible for extracting structured fields from PDF or HTML paystubs.  Normalizes provider‑specific formats (ADP, Workday, etc.). |
| **IncomeAnalyzer** | Computes trends, variance, stability and detection of unusual events across multiple years of income data. |
| **TaxExplainer**   | Provides human‑readable explanations for each line item on a paystub or W‑2 and general tax concepts. |
| **EducationAgent** | Retrieves educational content from the Knowledge Agent and tailors it to the user’s context. |

## Inputs & Outputs

* **Inputs:** Raw PDF W‑2s and paystubs stored in `data/raw/`; user questions about taxes or income; configuration settings (e.g. state of residence).
* **Outputs:** Structured records (`W2Record`, `PaystubRecord`), charts of income trends, textual explanations and interactive educational content.

## Open Questions

* Which PDF parsing library offers the best trade‑off between accuracy and ease of use?
* How should we handle benefits and deductions that vary by employer or state?  A configuration file per employer/state might be needed.
* How should we model tax brackets and credits over multiple years in a flexible way?

Further details will be fleshed out as we progress through Phase 2 of the roadmap.