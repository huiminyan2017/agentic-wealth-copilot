"""Storage helpers for Agentic Wealth Copilot.

This module defines where data is stored on disk and ensures that
directories exist.  Raw personal documents live in ``data/raw/`` and
should never be committed to version control.  Sanitized samples live in
``data/samples/`` for testing and documentation.
"""

from pathlib import Path

# Determine the project root by ascending three levels from this file.
REPO_ROOT = Path(__file__).resolve().parents[3]

DATA_DIR = REPO_ROOT / "data"
ORIGINAL_DATA_DIR = DATA_DIR / "raw"
PARSED_DATA_DIR   = DATA_DIR / "parsed"
SAMPLES_DIR = DATA_DIR / "samples"
SCHEMAS_DIR = DATA_DIR / "schemas"

# PDF (data/raw) → parse → validate → JSON (data/parsed) → analysis → explanation

def ensure_dirs() -> None:
    """Ensure that data directories exist.

    This function creates ``data/raw``, ``data/samples`` and ``data/schemas``
    directories if they do not already exist.  It is idempotent.
    """
    ORIGINAL_DATA_DIR.mkdir(parents=True, exist_ok=True)
    PARSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    SCHEMAS_DIR.mkdir(parents=True, exist_ok=True)

def repo_root() -> Path:
    # backend/app/services/storage.py -> .../agentic-wealth-copilot
    return Path(__file__).resolve().parents[3]

def parsed_dir(person: str) -> Path:
    p = PARSED_DATA_DIR / person
    p.mkdir(parents=True, exist_ok=True)
    (p / "w2").mkdir(exist_ok=True)
    (p / "paystub").mkdir(exist_ok=True)
    return p

def debug_dir(person: str) -> Path:
    p = parsed_dir() / "_debug"
    p.mkdir(parents=True, exist_ok=True)
    return p
