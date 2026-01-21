from __future__ import annotations

import os
import json
import re
import logging
from typing import Optional
from pathlib import Path
# from datetime import date, datetime
from backend.app.schemas import W2Record
from backend.app.services.storage import parsed_dir, repo_root
from backend.app.constants import EMPLOYER_MICROSOFT, EMPLOYER_U_OF_UTAH, EMPLOYER_UNKNOWN
from backend.app.services.utils import extract_pdf_text

logger = logging.getLogger(__name__)

def money(s: str) -> float:
    # "6,719.96" -> 6719.96
    return float(s.replace(",", "").replace("$", "").strip())

def find_money(pattern: str, text: str):
    m = re.search(pattern, text, re.IGNORECASE)
    return money(m.group(1)) if m else None

def _infer_year(name: str) -> int:
    import re
    m = re.search(r"(20\d{2})", name)
    return int(m.group(1)) if m else 0

def money(s: str) -> float:
    # "$6,719.96" -> 6719.96
    return float(s.replace(",", "").replace("$", "").strip())

def find_money(pattern: str, text: str) -> Optional[float]:
    m = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
    return money(m.group(1)) if m else None

def find_two_money(pattern: str, text: str) -> tuple[Optional[float], Optional[float]]:
    """
    Return (current, ytd) if the line has two numbers.
    """
    m = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
    if not m:
        return None, None
    return money(m.group(1)), money(m.group(2))

def _safe_relpath(p: Path) -> str:
    try:
        return p.relative_to(repo_root()).as_posix()
    except Exception:
        return str(p)

def _write_extracted_text(person: str, sha8: str, text: str) -> str:
    """
    Save extracted PDF text to data/parsed/<person>/_extracted_text/<sha8>.txt
    Return rel path for storage in record.
    """
    out_dir = parsed_dir(person) / "_extracted_text"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{sha8}.txt"
    out_path.write_text(text, encoding="utf-8", errors="ignore")
    return _safe_relpath(out_path)


def parse_w2(pdf_path: Path, employer: str, person: str, sha8: str) -> W2Record:
    """
    Parse a Microsoft W-2 locally (text-based PDF).
    Flexible parse: fill what we can + warnings for missing fields.
    """
    extracted_text = extract_pdf_text(pdf_path)
    extracted_text_rel = _write_extracted_text(person, sha8, extracted_text)

    # ---- Infer year ----
    year = _infer_year(pdf_path.name)
    if not year:
        # Try to find a year inside the text
        m = re.search(r"\b(20\d{2})\b", extracted_text)
        if m:
            year = int(m.group(1))

    # ---- Core boxes ----
    # These patterns are tolerant and can be refined as we see real text

    wages = find_money(r"\bBox\s*1\b.*?Wages.*?([0-9,]+\.\d{2})", extracted_text) \
        or find_money(r"\bWages,?\s*tips,?\s*other\s*compensation\b.*?([0-9,]+\.\d{2})", extracted_text)

    federal_tax_withheld = find_money(
        r"\bBox\s*2\b.*?Federal.*?tax.*?withheld.*?([0-9,]+\.\d{2})",
        extracted_text,
    ) or find_money(
        r"\bFederal\s*income\s*tax\s*withheld\b.*?([0-9,]+\.\d{2})",
        extracted_text,
    )

    ss_wages = find_money(
        r"\bBox\s*3\b.*?Social\s*security\s*wages\b.*?([0-9,]+\.\d{2})",
        extracted_text,
    )

    ss_tax_withheld = find_money(
        r"\bBox\s*4\b.*?Social\s*security\s*tax\s*withheld\b.*?([0-9,]+\.\d{2})",
        extracted_text,
    )

    medicare_wages = find_money(
        r"\bBox\s*5\b.*?Medicare\s*wages\b.*?([0-9,]+\.\d{2})",
        extracted_text,
    )

    medicare_tax_withheld = find_money(
        r"\bBox\s*6\b.*?Medicare\s*tax\s*withheld\b.*?([0-9,]+\.\d{2})",
        extracted_text,
    )

    # ---- State (optional) ----
    state_wages = find_money(
        r"\bBox\s*16\b.*?State\s*wages\b.*?([0-9,]+\.\d{2})",
        extracted_text,
    )

    state_tax_withheld = find_money(
        r"\bBox\s*17\b.*?State\s*income\s*tax\b.*?([0-9,]+\.\d{2})",
        extracted_text,
    )

    rec = W2Record(
        year=year or 0,
        employer_name=employer,
        wages=wages,
        federal_tax_withheld=federal_tax_withheld,
        ss_wages=ss_wages,
        ss_tax_withheld=ss_tax_withheld,
        medicare_wages=medicare_wages,
        medicare_tax_withheld=medicare_tax_withheld,
        state_wages=state_wages,
        state_tax_withheld=state_tax_withheld,
        extracted_text_path=extracted_text_rel,
        source_pdf_relpath=_safe_relpath(pdf_path),
        notes=f"local parse: {pdf_path.name}",
    )

    # ---- Missing-field warnings ----
    core_fields = [
        "wages",
        "federal_tax_withheld",
        "ss_wages",
        "ss_tax_withheld",
        "medicare_wages",
        "medicare_tax_withheld",
    ]

    missing = [f for f in core_fields if getattr(rec, f, None) is None]
    rec.missing_fields = missing

    if missing:
        rec.warnings.append(
            f"Missing {len(missing)} core W-2 fields: {', '.join(missing)}"
        )

    if not year:
        rec.warnings.append("Tax year not detected from filename or text")

    return rec