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
RAW_DIR = DATA_DIR / "raw"
SAMPLES_DIR = DATA_DIR / "samples"
SCHEMAS_DIR = DATA_DIR / "schemas"


def ensure_dirs() -> None:
    """Ensure that data directories exist.

    This function creates ``data/raw``, ``data/samples`` and ``data/schemas``
    directories if they do not already exist.  It is idempotent.
    """
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    SCHEMAS_DIR.mkdir(parents=True, exist_ok=True)