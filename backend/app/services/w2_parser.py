from __future__ import annotations

import os
import json
import re
import logging
from typing import Optional
from pathlib import Path
# from datetime import date, datetime
from backend.app.schemas import W2Record
from backend.app.services.paths import parsed_dir, repo_root
from backend.app.constants import EMPLOYER_MICROSOFT, EMPLOYER_U_OF_UTAH, EMPLOYER_UNKNOWN
from backend.app.services.pdf_utils import extract_pdf_text

logger = logging.getLogger(__name__)

def money(s: str) -> float:
    # "$6,719.96" -> 6719.96
    return float(s.replace(",", "").replace("$", "").strip())

def find_money(pattern: str, text: str) -> Optional[float]:
    m = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
    return money(m.group(1)) if m else None

def _infer_year(name: str) -> int:
    m = re.search(r"(20\d{2})", name)
    return int(m.group(1)) if m else 0

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
    # Microsoft W2s have labels on one line and values on the next line
    # Pattern: "1 Wages, tips, other comp. 2 Federal income tax withheld\n203009.69 34325.44"
    
    # Box 1 & 2: Wages and Federal Tax (appear together on consecutive lines)
    box_1_2_pattern = r"1\s+Wages,?\s*tips,?\s*other\s*comp\.\s*2\s+Federal\s*income\s*tax\s*withheld.*?\n\s*([0-9,]+\.\d{2})\s+([0-9,]+\.\d{2})"
    m = re.search(box_1_2_pattern, extracted_text, re.IGNORECASE | re.DOTALL)
    wages = money(m.group(1)) if m else None
    federal_tax_withheld = money(m.group(2)) if m else None

    # Box 3 & 4: SS Wages and SS Tax (appear together on consecutive lines)
    box_3_4_pattern = r"3\s+Social\s*security\s*wages\s*4\s+Social\s*security\s*tax\s*withheld.*?\n\s*([0-9,]+\.\d{2})\s+([0-9,]+\.\d{2})"
    m = re.search(box_3_4_pattern, extracted_text, re.IGNORECASE | re.DOTALL)
    ss_wages = money(m.group(1)) if m else None
    ss_tax_withheld = money(m.group(2)) if m else None

    # Box 5 & 6: Medicare Wages and Medicare Tax (appear together on consecutive lines)
    box_5_6_pattern = r"5\s+Medicare\s*wages\s*and\s*tips\s*6\s+Medicare\s*tax\s*withheld.*?\n\s*([0-9,]+\.\d{2})\s+([0-9,]+\.\d{2})"
    m = re.search(box_5_6_pattern, extracted_text, re.IGNORECASE | re.DOTALL)
    medicare_wages = money(m.group(1)) if m else None
    medicare_tax_withheld = money(m.group(2)) if m else None

    # ---- State (optional) ----
    # Box 16 & 17: State wages and State tax
    # Handle both spaced and non-spaced formats:
    # - "16 State wages, tips, etc.\nUT ... 203009.69\n17 State income tax\n9027.31"
    # - "16Statewages,tips,etc.\nUT 11860828004WTH 210078.31\n17Stateincometax\n10149.03"
    state_pattern = r"16\s*State\s*wages,?\s*tips,?\s*etc\.\s*\n\s*[A-Z]{2}\s+\S+\s+([0-9,]+\.\d{2})\s*\n\s*17\s*State\s*income\s*tax.*?\n\s*([0-9,]+\.\d{2})"
    m = re.search(state_pattern, extracted_text, re.IGNORECASE | re.DOTALL)
    state_wages = money(m.group(1)) if m else None
    state_tax_withheld = money(m.group(2)) if m else None

    # ---- Box 12 codes ----
    # Box 12 contains various employer codes with amounts
    # Common codes: C (GTL), D (401k), W (HSA), AA (Roth 401k)
    # Format varies: "12b D 21850.44" or "12bD 21850.44" or "D 21850.44"
    
    # Code C: Taxable group-term life insurance over $50k
    box12_gtl = None
    m = re.search(r"(?:12[a-d]?\s*)?C\s+([0-9,]+\.\d{2})", extracted_text)
    if m:
        box12_gtl = money(m.group(1))
    
    # Code D: 401(k) elective deferrals (pre-tax)
    box12_401k_pretax = None
    m = re.search(r"(?:12[a-d]?\s*)?D\s+([0-9,]+\.\d{2})", extracted_text)
    if m:
        box12_401k_pretax = money(m.group(1))
    
    # Code W: HSA employer contributions
    box12_hsa = None
    m = re.search(r"(?:12[a-d]?\s*)?W\s+([0-9,]+\.\d{2})", extracted_text)
    if m:
        box12_hsa = money(m.group(1))
    
    # Code AA: Roth 401(k) contributions
    box12_roth_401k = None
    m = re.search(r"(?:12[a-d]?\s*)?AA\s+([0-9,]+\.\d{2})", extracted_text)
    if m:
        box12_roth_401k = money(m.group(1))

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
        box12_401k_pretax=box12_401k_pretax,
        box12_hsa=box12_hsa,
        box12_roth_401k=box12_roth_401k,
        box12_gtl=box12_gtl,
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

    # SS wage base cap check (26 U.S.C. § 3121).  Box 3 wages cannot legally
    # exceed the annual SSA limit; a higher value likely means a parsing error.
    _ss_limits = {2018: 128400, 2019: 132900, 2020: 137700, 2021: 142800,
                  2022: 147000, 2023: 160200, 2024: 168600, 2025: 176100}
    if rec.year in _ss_limits and rec.ss_wages is not None:
        cap = _ss_limits[rec.year]
        if rec.ss_wages > cap:
            rec.warnings.append(
                f"SS wages {rec.ss_wages:,.2f} exceed {rec.year} wage base cap "
                f"{cap:,.0f} — possible parsing error"
            )

    logger.info(f"Parsed W2: {rec}")
    return rec