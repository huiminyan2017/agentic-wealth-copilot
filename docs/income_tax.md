# Income & Tax Module

The Income & Tax module handles W-2 and paystub parsing, income trend analysis, and tax intelligence.
Parsing is fully deterministic — no LLM, no hallucinations. The LLM is only used at the end to
narrate the finished analysis report in plain English.

---

## Features

- **Paystub parsing** — extract gross pay, deductions, taxes, net pay with arithmetic validation
- **W-2 parsing** — extract wages, withholdings, Box 12 codes, SS wage-cap checks
- **Income trends** — monthly/yearly aggregation with charts
- **Income analysis pipeline** — 6-step deterministic pipeline: anomaly detection, insights, recommended actions

---

## Data Schemas

### W-2 Record

Extracted from W-2 PDFs and stored as JSON in `data/parsed/<person>/w2/`.

| Field | Type | Description |
|-------|------|-------------|
| `year` | int | Tax year |
| `employer_name` | str | Employer identifier (`microsoft`, `u_of_utah`) |
| `wages` | float | Box 1 — Wages, tips, other compensation |
| `federal_tax_withheld` | float | Box 2 — Federal income tax withheld |
| `ss_wages` | float | Box 3 — Social Security wages (capped at annual limit) |
| `ss_tax_withheld` | float | Box 4 — Social Security tax withheld |
| `medicare_wages` | float | Box 5 — Medicare wages and tips |
| `medicare_tax_withheld` | float | Box 6 — Medicare tax withheld |
| `state_wages` | float | Box 16 — State wages |
| `state_tax_withheld` | float | Box 17 — State income tax |
| `box12_401k_pretax` | float | Box 12 Code D — 401(k) elective deferrals (pre-tax) |
| `box12_hsa` | float | Box 12 Code W — HSA employer contributions |
| `box12_roth_401k` | float | Box 12 Code AA — Roth 401(k) contributions |
| `box12_gtl` | float | Box 12 Code C — Taxable group-term life insurance over $50k |
| `missing_fields` | list | Fields not found during parsing |
| `warnings` | list | Parsing warnings (e.g. SS wage cap violation) |

#### Social Security Wage Cap

The parser enforces IRS Social Security wage base limits (26 U.S.C. § 3121). Box 3 (SS wages)
can never legally exceed the annual cap. If `ss_wages` exceeds the cap for the W-2's year,
a warning is appended to `warnings`.

| Year | SS Wage Base Cap |
|------|-----------------|
| 2018 | $128,400 |
| 2019 | $132,900 |
| 2020 | $137,700 |
| 2021 | $142,800 |
| 2022 | $147,000 |
| 2023 | $160,200 |
| 2024 | $168,600 |
| 2025 | $176,100 |
| 2026 | $180,000 |

### Paystub Record

Extracted from paystub PDFs and stored as JSON in `data/parsed/<person>/paystub/`.

| Field | Type | Description |
|-------|------|-------------|
| `pay_date` | date | Pay date (YYYY-MM-DD) |
| `employer_name` | str | `microsoft` or `u_of_utah` |
| `gross` | object | `{value, details: {base, stock, bonus, perks, vacation_po, shared_success_bonus}}` |
| `pretax_deductions` | object | `{value, details: {401k, hsa_ee, fsa_dep_care, fsa_limited_vision_dental}}` |
| `taxes` | object | `{value, details: {federal, state, ss, medicare}}` |
| `aftertax_deductions` | object | `{value, details: {401k, 401k-roth, espp, espp_refund, add_insurance, life_dep_insurance, giving_program}}` |
| `net_pay` | object | `{value}` — take-home amount |
| `stock_pay` | object | `{value, details: {income, tax}}` — RSU/stock award offset |
| `ytd` | object | `{gross, net_pay, federal_tax, state_tax, ss_tax, medicare_tax}` |
| `validation` | object | `{net_pay_diff, tax_sum_diff, pretax_sum_diff, aftertax_sum_diff}` — all should be 0.0 |

### Unified Schema Design

Both W-2 and paystub records use a **single unified schema** regardless of employer. This means:

- **Consistent aggregation** — income trends and tax calculations work uniformly across employers
- **Flexible details** — the `details` dicts accommodate employer-specific line items without schema changes
- **Sparse fields** — optional fields (e.g. `stock_pay`) are `null` when not applicable
- **Easy extensibility** — adding a new employer only requires a new parser, not schema changes

The parser (`backend/app/services/paystub_parser.py`, `w2_parser.py`) handles employer-specific
PDF layouts and normalizes output to the common schema.

---

## File Organization

```
data/
├── raw/<Person>/
│   ├── paystub/                          # Original paystub PDFs
│   ├── paystub_groundtruth/              # Expected parsed values for testing
│   ├── w2/                               # Original W-2 PDFs
│   └── w2_groundtruth/                   # Expected parsed values for testing
└── parsed/<Person>/
    ├── paystub/                          # Parsed JSON files
    ├── w2/                               # Parsed JSON files
    └── income_file_index.json            # Document index
```

### File Naming Convention

| Document | Format | Example |
|----------|--------|---------|
| Paystub | `<Employer>-Paystub-YYYY-MM-DD.pdf` | `Microsoft-Paystub-2018-04-15.pdf` |
| W-2 | `<Employer>-W2-YYYY.pdf` | `Microsoft-W2-2018.pdf` |

---

## Validation

The parser checks 4 arithmetic invariants on every paystub. All diffs are stored in the
`validation` object and displayed in the UI — a non-zero diff flags a parsing problem.

| # | Check | Formula | Tolerance |
|---|-------|---------|-----------|
| 1 | Net pay | `gross - net_pay - stock_pay - taxes - pretax - aftertax ≈ 0` | $1.00 |
| 2 | Taxes | `taxes.value = sum(taxes.details)` | $0.01 |
| 3 | Pre-tax | `pretax_deductions.value = sum(pretax_deductions.details)` | $0.01 |
| 4 | After-tax | `aftertax_deductions.value = sum(aftertax_deductions.details)` | $0.01 |

Status indicators: ✅ Pass · 🟡 Warning · ❌ Fail · ⬜ N/A

---

## Income Analysis Pipeline  (`agents/income_analysis.py`)

A 6-step deterministic Python pipeline — **no LLM anywhere in this file**. The LLM only sees
the finished Markdown report afterward, inside the `income_tax` copilot node.

```
load_data → compute_trends → detect_anomalies → generate_insights → propose_actions → compile_report
```

### Person-aware routing

The routing node extracts person names from the user's message and sets `state.person` so the
`income_tax` node loads data from the correct `data/parsed/<person>/` folder.

### Anomaly detection

- **Tax rate changes** — year-over-year effective tax rate shifts > 3%
- **Income volatility** — high coefficient of variation in monthly gross
- **SS cap hit** — Social Security wages ≥ 95% of the annual limit
- **Stock income patterns** — sporadic stock compensation causing month-to-month volatility
- **Deduction changes** — month-over-month deduction shifts > 20%

### Insight categories

- **Tax optimization** — high effective rate, HSA/401(k) under-contribution, SS cap reached
- **Retirement** — 401(k) contribution gap vs. annual IRS limit
- **Income stability** — growth or decline patterns

### Recommended actions

- Increase 401(k) or HSA contributions (with dollar amounts and estimated tax savings)
- Review W-4 withholding
- Consider tax planning consultation for high earners (backdoor Roth, ESPP, options)

---

## API Endpoints

### `GET /api/income/scan`

Scan raw folders for unprocessed documents.

```
GET /api/income/scan?person=DemoMicrosoftEmployee
```

### `POST /api/income/ingest`

Ingest and parse documents, writing results to `data/parsed/`.

```json
{
  "person": "DemoMicrosoftEmployee",
  "rel_paths": ["data/raw/DemoMicrosoftEmployee/paystub/Microsoft-Paystub-2018-04-15.pdf"]
}
```

### `GET /api/income/trends`

Get income trends and analytics for the Income & Tax page charts.

```
GET /api/income/trends?person=DemoMicrosoftEmployee
```

### `POST /api/income/analyze`

Run the income analysis pipeline directly (also triggered by the copilot when intent = `income_tax`).

```json
{ "person": "DemoMicrosoftEmployee" }
```

Returns: `report`, `insights`, `actions`, `anomalies`, `trends`, `data_summary`, `trace`

---

## CLI Tools

### Ground truth management  (`scripts/income_groundtruth_tool.py`)

```bash
# Check parser output against groundtruth
python scripts/income_groundtruth_tool.py paystub check
python scripts/income_groundtruth_tool.py w2 check

# Regenerate groundtruth (run after parser changes)
python scripts/income_groundtruth_tool.py paystub save --force
python scripts/income_groundtruth_tool.py w2 save --force
```

### Document ingestion  (`scripts/income_ingest_tool.py`)

```bash
# Ingest all document types for all persons
python scripts/income_ingest_tool.py all

# Force re-ingest (overwrite existing parsed JSON)
python scripts/income_ingest_tool.py paystub --force
python scripts/income_ingest_tool.py w2 --force
```

---

## Testing

Tests automatically discover all `Demo*` users under `data/raw/` and run against each one.
Groundtruth comparison uses a recursive `_assert_json_match()` helper that compares every field
(floats within $0.01 tolerance). The only skipped key is `_disclaimer` — a synthetic-data notice
added by the generate script, not returned by the parser.

### Demo Users

| User | Documents | Notes |
|------|-----------|-------|
| `DemoMicrosoftEmployee` | 4 paystubs (2018), 1 W-2 (2018) | ADP-style 2-page paystub; Box 12 codes C/D/W/AA; ESPP |
| `DemoUofUEmployee` | 1 paystub (2024), 1 W-2 (2024) | Single-page UofU format; Box 12 code D (403b) |

All values are synthetic. Years 2018 (Microsoft) and 2024 (UofU) make it obviously fake.

### Regenerating demo data

```bash
python scripts/generate_demo_user_paystub_w2.py
python -m pytest "tests/test_paystub_ingest_&_parse.py" "tests/test_w2_ingest_&_parse.py" -v
```

### Running tests

```bash
# All income tests
python -m pytest "tests/test_paystub_ingest_&_parse.py" "tests/test_w2_ingest_&_parse.py" -v

# Filter by demo user
python -m pytest "tests/test_paystub_ingest_&_parse.py" -v -k "Microsoft"
python -m pytest "tests/test_w2_ingest_&_parse.py" -v -k "UofU"
```

### Test coverage

**`test_paystub_ingest_&_parse.py`**
- `TestParserGroundtruth` — full JSON comparison against groundtruth for every Demo* user
- `TestIngestionPipeline` — end-to-end: JSON creation, index, filename format, deduplication

**`test_w2_ingest_&_parse.py`**
- `TestW2ParserGroundtruth` — full JSON comparison against groundtruth for every Demo* user
- `TestW2ParserValidation` — domain checks: federal tax rate 5–50%, SS wages within annual cap
- `TestW2Detection` — `detect_doc_kind` and `detect_employer` filename classification
- `TestIngestionPipeline` — end-to-end: JSON creation, index, deduplication
