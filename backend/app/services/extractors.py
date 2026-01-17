"""PDF extraction utilities for W‑2 and paystub documents.

This module defines helper functions to convert raw PDF documents into
structured Pydantic models defined in :mod:`backend.app.schemas`.  The
current implementation is intentionally naive: it infers the tax year
or pay date from the filename and returns empty or None values for
monetary fields.  In a production environment you should replace
these heuristics with robust PDF parsing logic (e.g. using
``pdfplumber`` or ``pdfminer.six``) and extract each box or line
item explicitly.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Optional

from backend.app.schemas import W2Record, PaystubRecord

FLOAT_RE = re.compile(r"\d{1,3}(?:,\d{3})*(?:\.\d{2})")


def _parse_year_from_filename(path: Path) -> Optional[int]:
    """Attempt to extract a four‑digit year from a filename.

    Args:
        path: Path object pointing to the PDF file.

    Returns:
        An integer year if found, otherwise ``None``.
    """
    m = re.search(r"(\d{4})", path.stem)
    return int(m.group(1)) if m else None


def extract_w2(pdf_path: str) -> W2Record:
    """Extract a W‑2 record from a PDF file.

    This placeholder implementation only infers the tax year from the
    filename.  All monetary fields are set to ``0.0`` or ``None``.  To
    implement real extraction, consider using a PDF parsing library to
    locate the boxes and capture their numeric values.

    Args:
        pdf_path: Absolute or relative path to the W‑2 PDF.

    Returns:
        A :class:`W2Record` populated with available data.
    """
    path = Path(pdf_path)
    year = _parse_year_from_filename(path) or 0
    return W2Record(
        year=year,
        employer_name="",
        wages=0.0,
        federal_tax_withheld=0.0,
        ss_wages=0.0,
        ss_tax_withheld=0.0,
        medicare_wages=0.0,
        medicare_tax_withheld=0.0,
        state_wages=None,
        state_tax_withheld=None,
        notes="Extraction not implemented",
    )


def extract_paystub(pdf_path: str) -> PaystubRecord:
    """Extract a paystub record from a PDF file.

    This placeholder implementation infers the pay date from the
    filename using the pattern ``YYYY-MM-DD``.  Monetary fields
    default to ``0.0``.  Replace with real parsing logic as needed.

    Args:
        pdf_path: Absolute or relative path to the paystub PDF.

    Returns:
        A :class:`PaystubRecord` populated with available data.
    """
    path = Path(pdf_path)
    m = re.search(r"(\d{4}-\d{2}-\d{2})", path.stem)
    pay_date = date.fromisoformat(m.group(1)) if m else date.today()
    return PaystubRecord(
        pay_date=pay_date,
        employer_name="",
        gross_pay=0.0,
        pre_tax_deductions=0.0,
        post_tax_deductions=0.0,
        taxable_wages=0.0,
        federal_tax=0.0,
        ss_tax=0.0,
        medicare_tax=0.0,
        state_tax=0.0,
        other_taxes=0.0,
        net_pay=0.0,
        ytd_gross=0.0,
        ytd_taxable_wages=0.0,
        ytd_federal_tax=0.0,
        ytd_state_tax=0.0,
        ytd_ss_tax=0.0,
        ytd_medicare_tax=0.0,
        notes="Extraction not implemented",
    )
