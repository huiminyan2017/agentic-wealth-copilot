# Project Rules for Claude

## Package Management

**Any package installed with `pip install` during a session must also be added to `requirements.txt` before the session ends.**

- Add it under the relevant comment section (e.g. `# Stock market data`, `# Testing`)
- Use `>=` with the current major.minor version (e.g. `yfinance>=0.2.40`)
- This applies even for one-off installs or quick experiments

## Virtual Environment

Always use `.venv/bin/python` and `.venv/bin/pip` (never the system `python`/`pip`).
The project's virtualenv is at `.venv/`.

## Demo Data

- Demo data lives in `data/raw/DemoMicrosoftEmployee/` — all values are synthetic/fake
- Never copy real user values (wages, taxes, HSA amounts, etc.) into DemoMicrosoftEmployee files
- DemoMicrosoftEmployee uses year 2018 dates to make it obviously fake
- All DemoMicrosoftEmployee groundtruth JSONs must include a `_disclaimer` field

## Generating DemoMicrosoftEmployee Test Data

- Paystubs: `python scripts/generate_test_paystubs.py`
- W2: `python scripts/generate_test_w2.py`
- Both scripts auto-regenerate groundtruth JSONs by running the real parser
- After regenerating, run `python -m pytest tests/test_paystub_parser.py tests/test_w2_parser.py -v` to confirm tests pass

## Git

- `.DS_Store` files are in `.gitignore` — never commit them
- `data/raw/*` is ignored except `data/raw/DemoMicrosoftEmployee/`
- `data/parsed/` is ignored
