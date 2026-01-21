from __future__ import annotations

import os
import re
# from dataclasses import dataclass
# from datetime import date
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List
import pdfplumber
# from backend.app.services.storage import debug_dir
from backend.app.constants import EMPLOYER_MICROSOFT
import logging
from backend.app.services.utils import detect_employer, extract_pdf_text

logger = logging.getLogger(__name__)


def find_pay_date(text: str) -> Optional[str]:
    """
    Extract pay date in ISO format (YYYY-MM-DD) from Microsoft paystub text.

    Pay dates can appear under several headers depending on the template:
      - Advice Date: 01/15/2026
      - Period Beg/End: 01/01/2026 01/15/2026  (use the end date)
      - Pay Date: Jan 31, 2024
      - Period End Date: Jan 31, 2024

    This function tries multiple patterns and normalizes the date to ISO format.
    """
    # Candidate patterns with a capturing group for the date portion.
    patterns = [
        # Advice Date: 01/15/2026
        r"Advice\s+Date\s*:?\s*(\d{2}/\d{2}/\d{4})",
        # Period Beg/End: 01/01/2026 01/15/2026 (take the second date)
        r"Period\s+Beg/End\s*:?\s*\d{2}/\d{2}/\d{4}\s+(\d{2}/\d{2}/\d{4})",
        # Check Date 01/15/2026 or Check Date: 01/15/2026
        r"Check\s+Date\s*:?\s*(\d{2}/\d{2}/\d{4})",
        # Pay Date: Jan 31, 2024 or Period End Date: Jan 31, 2024
        r"(?:Pay Date|Period End Date)\s*:?\s*([A-Za-z]{3}\s+\d{1,2},\s+\d{4})",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            date_str = m.group(1).strip()
            for fmt in ("%m/%d/%Y", "%b %d, %Y"):
                try:
                    dt = datetime.strptime(date_str, fmt)
                    return dt.strftime("%Y-%m-%d")
                except ValueError:
                    continue
    return None


"""
Simple MSFT paystub parser using pdfplumber
-------------------------------------------

This module defines a single helper function, :func:`parse_paystub_msft_simple`,
which extracts the summary values from a Microsoft paystub PDF.  The goal is
to return a small dictionary of numeric fields for the current period and year‐to‐date
totals.  We intentionally avoid complex layout heuristics and instead rely
solely on anchored label rows.  The parser works with both the older
"Earnings Statement" format as well as the newer "Official Copy" format used by
Microsoft circa 2025–2026.  In either case the summary section contains a
handful of predictable rows:

* **Total Earnings** – the current period gross pay as well as the YTD gross
  pay.  Earlier statements sometimes label this row "TOTAL EARNINGS" or
  "GROSS PAY"; we normalize the search to any of those terms.  We treat this
  row as the authoritative source for both the current and YTD gross numbers.

* **Net Pay** – the take‑home pay for the period and sometimes a YTD total.

* **Taxable Earnings** – the taxable wages (current period and YTD).  If a
  statement does not include this line we attempt a fallback by searching for
  paragraphs such as "Federal taxable wages for the period" and
  "Federal taxable wages for the year".

* **Federal Income Tax**, **Social Security Tax**, **Medicare Tax** – taxes
  withheld during the current period.  Each of these rows usually has two
  columns (current and YTD).  If a given label appears only once on the page
  (rare) we assume the value corresponds to the current period.

* **State tax** – The state withholding line differs across statements.  On
  older statements the label reads "WITHHOLDING – UT" (or another two letter
  state abbreviation); on newer statements it reads "UT W/H TAX" or
  "STATE TAX".  We provide multiple regular expressions to match any of these
  variations.  As with the other tax rows we parse both the current and YTD
  amounts.

The parser extracts the text of each page using ``pdfplumber`` and then
splits the text by newline.  It scans for lines matching one of the known
labels and then attempts to locate numeric values on that same line.  When
two money values appear on a line we treat them as "current" and "YTD"
respectively; when only one value appears we assume it is the current
period amount.  Numbers are converted to floats by removing commas and
parens (parentheses) and handling negative values appropriately.  If a value
cannot be parsed it is returned as ``None``.

While this parser is not guaranteed to handle every possible edge case, it
provides a straightforward and deterministic baseline for parsing Microsoft
paystub PDFs without relying on network calls or AI models.  If the format
changes significantly a more sophisticated approach may be necessary.

Example usage:

>>> from pathlib import Path
>>> from .paystub_msft_parser import parse_paystub_msft_simple
>>> res = parse_paystub_msft_simple(Path("/path/to/paystub.pdf"))
>>> print(res["gross_pay"], res["net_pay"])
6507.46 2301.61

"""
def parse_paystub_msft_simple(pdf_path: Path) -> Dict[str, Optional[float]]:
    """Parse a Microsoft paystub PDF and return a summary dictionary.

    :param pdf_path: The path to the PDF file to parse.
    :returns: A dictionary containing the extracted summary values.  Each key
              corresponds to a summary metric (e.g. ``gross_pay``,
              ``federal_tax``, ``ytd_taxable_wages``).  Any value that
              cannot be extracted will be ``None``.

    The returned dictionary has the following keys:

    ``pay_date``: Optional[str]
        The date of the pay period.  This implementation does not attempt
        to extract the pay date and always returns ``None``.

    ``employer_name``: str
        Always set to ``"microsoft"``.

    ``gross_pay``: Optional[float]
        The current period gross pay, pulled from the ``Total Earnings`` row.

    ``net_pay``: Optional[float]
        The take‑home pay for the current period.

    ``taxable_wages``: Optional[float]
        The current period taxable wages (aka taxable earnings).

    ``federal_tax``: Optional[float]
        Federal income tax withheld during the current period.

    ``ss_tax``: Optional[float]
        Social security tax withheld during the current period.

    ``medicare_tax``: Optional[float]
        Medicare tax withheld during the current period.

    ``state_tax``: Optional[float]
        State tax (withholding) for the current period.

    ``ytd_gross``: Optional[float]
        Year‑to‑date gross pay.

    ``ytd_taxable_wages``: Optional[float]
        Year‑to‑date taxable wages.

    ``ytd_federal_tax``: Optional[float]
        Year‑to‑date federal income tax withheld.

    ``ytd_ss_tax``: Optional[float]
        Year‑to‑date social security tax withheld.

    ``ytd_medicare_tax``: Optional[float]
        Year‑to‑date medicare tax withheld.

    ``ytd_state_tax``: Optional[float]
        Year‑to‑date state tax withheld.

    ``ytd_net_pay``: Optional[float]
        Year‑to‑date net pay (if present).

    ``warnings``: List[str]
        A list of textual warnings describing any heuristics or fallbacks
        encountered during parsing.

    ``source_pdf``: str
        The path of the PDF file as a string.

    ``parser``: str
        The name of this parser (``"msft_pdfplumber_simple"``).

    """
    # Extract text from the PDF.
    all_text = ""
    lines: List[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            all_text += page_text + "\n"
            lines.extend(page_text.splitlines())

    # Normalize whitespace
    lines = [l.strip() for l in lines if l.strip()]

    # Precompile regexes for each label category.  We anchor at word
    # boundaries but otherwise allow arbitrary spacing to account for both
    # uppercase and mixed case labels.
    gross_patterns = [re.compile(r"\b(TOTAL\s+EARNINGS|GROSS\s+PAY)\b", re.IGNORECASE)]
    net_patterns = [re.compile(r"\bNET\s+PAY\b", re.IGNORECASE)]
    taxable_patterns = [re.compile(r"\bTAXABLE\s+EARNINGS\b", re.IGNORECASE)]
    federal_patterns = [re.compile(r"\bFEDERAL\s+INCOME\s+TAX\b", re.IGNORECASE)]
    ss_patterns = [re.compile(r"\bSOCIAL\s+SECURITY\s+TAX\b", re.IGNORECASE)]
    medicare_patterns = [re.compile(r"\bMEDICARE\s+TAX\b", re.IGNORECASE)]
    # State tax patterns cover several variants: "WITHHOLDING - UT", "UT W/H TAX", "STATE TAX"
    state_patterns = [
        re.compile(r"\bWITHHOLDING\s*-\s*[A-Z]{2,}\b", re.IGNORECASE),
        re.compile(r"\b[A-Z]{2}\s+W/H\s+TAX\b", re.IGNORECASE),
        re.compile(r"\bSTATE\s+TAX\b", re.IGNORECASE),
    ]

    gross, ytd_gross = _find_row_values(lines, gross_patterns)
    net, ytd_net = _find_row_values(lines, net_patterns)
    taxable, ytd_taxable = _find_row_values(lines, taxable_patterns)
    federal, ytd_federal = _find_row_values(lines, federal_patterns)
    ss, ytd_ss = _find_row_values(lines, ss_patterns)
    medicare, ytd_medicare = _find_row_values(lines, medicare_patterns)
    state, ytd_state = _find_row_values(lines, state_patterns)

    # Fallback for taxable wages if missing
    if taxable is None and ytd_taxable is None:
        taxable_fallback, ytd_taxable_fallback = _find_taxable_paragraphs(all_text)
        taxable = taxable or taxable_fallback
        ytd_taxable = ytd_taxable or ytd_taxable_fallback

    # Build result dictionary
    result: Dict[str, Optional[float]] = {
        "pay_date": find_pay_date(all_text),
        "employer_name": EMPLOYER_MICROSOFT,
        "gross_pay": gross,
        "net_pay": net,
        "taxable_wages": taxable,
        "federal_tax": federal,
        "ss_tax": ss,
        "medicare_tax": medicare,
        "state_tax": state,
        "ytd_gross": ytd_gross,
        "ytd_taxable_wages": ytd_taxable,
        "ytd_federal_tax": ytd_federal,
        "ytd_ss_tax": ytd_ss,
        "ytd_medicare_tax": ytd_medicare,
        "ytd_state_tax": ytd_state,
        "ytd_net_pay": ytd_net,
        "warnings": [],
        "source_pdf": str(pdf_path),
        "parser": "msft_pdfplumber_simple",
    }

    # Validation heuristics.  MSFT paystubs often contain a small hourly rate
    # (e.g. 86.67) which can be mistaken for the gross pay if the labels
    # aren't matched correctly.  If the gross pay is smaller than a typical
    # paycheck (e.g. < 300) we assume it is likely a rate and null it out.
    if result["gross_pay"] is not None and result["gross_pay"] < 300:
        result["warnings"].append(
            f"gross_pay looked too small ({result['gross_pay']}); likely a rate. Nulling."
        )
        result["gross_pay"] = None

    def _extract_money_tokens(line: str) -> List[str]:
        """Return a list of money tokens (numbers with optional commas, minus sign
        or parentheses) found in a line of text.  We deliberately avoid
        capturing units like ``$`` or ``USD``.

        Examples of valid tokens include ``6,507.46``, ``-2,015.99``, ``(2,015.99)``
        and ``0.00``.  Tokens are returned in the order they appear.

        """
        money_re = re.compile(r"(?<!\d)(?:\(?-?[\d,]+\.\d{2}\)?)(?!\d)")
        return money_re.findall(line)


    def _to_float(s: str) -> Optional[float]:
        """Convert a money string to float, handling commas and parentheses.

        Returns None if conversion fails.  Parentheses are treated as a
        negative sign.  For example ``"(2,015.99)"`` becomes -2015.99.
        """
        try:
            s_clean = s.strip()
            neg = False
            if s_clean.startswith("(") and s_clean.endswith(")"):
                neg = True
                s_clean = s_clean[1:-1]
            s_clean = s_clean.replace(",", "")
            value = float(s_clean)
            return -value if neg else value
        except Exception:
            return None


    def _find_row_values(lines: List[str], patterns: List[re.Pattern]) -> Tuple[Optional[float], Optional[float]]:
        """Search ``lines`` for the first line matching any regex in ``patterns`` and
        return the money values on that line.  If two values are found they are
        returned as (current, ytd).  If only one value is found the second
        element is None.  If no matching line is found return (None, None).

        We look for both column and row anchored patterns, matching anywhere
        within the line.
        """
        for line in lines:
            for pat in patterns:
                if pat.search(line):
                    tokens = _extract_money_tokens(line)
                    if not tokens:
                        return None, None
                    if len(tokens) >= 2:
                        return _to_float(tokens[0]), _to_float(tokens[1])
                    else:
                        return _to_float(tokens[0]), None
        return None, None


    def _find_taxable_paragraphs(text: str) -> Tuple[Optional[float], Optional[float]]:
        """Fallback parser for taxable wages when the "TAXABLE EARNINGS" row is
        missing.  Looks for paragraphs like ``"Federal taxable wages for the
        period: 4,352.03"`` and returns the number for the period and year.
        """
        m = re.search(r"Federal taxable wages for the period:\s*([\d,]+\.\d{2})",
                    text, re.IGNORECASE)
        current = _to_float(m.group(1)) if m else None
        m = re.search(r"Federal taxable wages for the year:\s*([\d,]+\.\d{2})",
                    text, re.IGNORECASE)
        ytd = _to_float(m.group(1)) if m else None
        return current, ytd

    return result


def parse_paystub_generic_simple(pdf_path: Path, employer_name: str = "unknown") -> Dict[str, Any]:
    """
    Generic parser for many paystubs (including many university/payroll PDFs).

    Strategy:
      - Extract text (pdfplumber)
      - Search for common labels: Gross Pay, Net Pay, Taxable Wages, FIT, SIT, SS, Medicare
      - This is intentionally simple: it won't handle every edge case, but it's good enough
        as a fallback BEFORE Azure.
    """
    text = extract_pdf_text(pdf_path, max_pages=2)

    result: Dict[str, Any] = {
        "pay_date": find_pay_date(text),
        "employer_name": employer_name,
        "gross_pay": _find_value_by_label(text, [r"\bGROSS\s+PAY\b", r"\bTOTAL\s+GROSS\b"]),
        "net_pay": _find_value_by_label(text, [r"\bNET\s+PAY\b"]),
        "taxable_wages": _find_value_by_label(text, [r"\bTAXABLE\s+WAGES\b", r"\bTAXABLE\s+EARNINGS\b", r"\bFED\s+TAXABLE\b"]),
        "federal_tax": _find_value_by_label(text, [r"\bFEDERAL\s+TAX\b", r"\bFED\s+INCOME\s+TAX\b", r"\bF\.?I\.?T\.?\b"]),
        "state_tax": _find_value_by_label(text, [r"\bSTATE\s+TAX\b", r"\bS\.?I\.?T\.?\b"]),
        "ss_tax": _find_value_by_label(text, [r"\bSOCIAL\s+SECURITY\b", r"\bOASDI\b"]),
        "medicare_tax": _find_value_by_label(text, [r"\bMEDICARE\b"]),
        "warnings": [],
        "source_pdf": str(pdf_path),
        "parser": "generic_pdfplumber_simple",
    }

    def _to_float_money(s: str) -> float:
        return float(s.replace(",", "").replace("$", "").strip())

    def _find_value_by_label(text: str, label_patterns: List[str], want_ytd: bool = False) -> Optional[float]:
        """
        MSFT paystub rule:
        Lines usually look like:
            LABEL    <rate?> <hours?> <this-period> <ytd>

        We extract ALL money values on the matched line:
        - want_ytd=False → second-to-last
        - want_ytd=True  → last
        """
        lines = text.splitlines()

        for line in lines:
            for pat in label_patterns:
                if re.search(pat, line, re.IGNORECASE):
                    # Find all money values on the line
                    nums = re.findall(r"[\d,]+\.\d{2}", line)
                    if not nums:
                        continue

                    try:
                        if want_ytd and len(nums) >= 2:
                            return _to_float_money(nums[-1])
                        elif not want_ytd:
                            if len(nums) >= 2:
                                return _to_float_money(nums[-2])
                            else:
                                return _to_float_money(nums[-1])
                    except Exception:
                        continue

        return None

    return result

def parse_paystub(pdf_path: Path, employee: str, prefer_azure: bool = False) -> Dict[str, Any]:
    """
    Hybrid strategy:

      1) Try pdfplumber text first (deterministic)
      2) Detect employer
      3) Use the employer-specific parser if known
      4) (TODO)If missing critical fields, fall back to Azure OCR-to-text

    prefer_azure=True means you want Azure first (generally NOT recommended for your use case).
    """
    assert prefer_azure == False, "Azure not implemented yet in parser"
    logger.info(f"parse_paystub_hybrid: pdf_path={pdf_path}, employee={employee}, prefer_azure={prefer_azure}")
    pdf_path = Path(pdf_path)

    text = extract_pdf_text(pdf_path, max_pages=2)
    emp = detect_employer(text)
    if emp != employee: 
        logger.error(f"Detected employer '{emp}' does not match expected '{employee}' for {pdf_path.name}")
        res["warnings"].append(f"Detected employer '{emp}' does not match expected '{employee}'")
        return res

    try:
        if emp == EMPLOYER_MICROSOFT:
            res = parse_paystub_msft_simple(pdf_path)
        else:
            res = parse_paystub_generic_simple(pdf_path, employer_name=emp)
    except Exception as e:
        logger.error(f"Local parser failed for {pdf_path.name}: {e}")
        res["warnings"].append(f"Local parser failed: {e}")
        return res
    
    logger.info(f"Parsed paystub: {res}")
    return res