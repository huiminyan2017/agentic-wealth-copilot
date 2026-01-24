"""
Paystub Parser - Structured format
==================================

This parser extracts financial data from PDF paystubs and outputs a structured format.

Output Schema:
{
  "pay_date": str,           # ISO format YYYY-MM-DD
  "employer_name": str,      # "microsoft" or "u_of_utah"
  
  "gross": {
    "value": float,          # Total gross pay
    "details": {
      "base": float,         # Base salary (MSFT & UoU)
      "stock": float,        # Stock Award Income (MSFT only)
      "perks": float,        # Perks+ Taxable benefits (MSFT only)
      "bonus": float,        # Reward Bonus (MSFT only)
      "vacation_po": float,  # Vacation payout (MSFT only)
      "shared_success_bonus": float  # Company-wide bonus (MSFT only)
    }
  },
  
  "pretax_deductions": {
    "value": float,          # Total pre-tax deductions (negative)
    "details": {
      "401k": float,         # 401K Pre Tax contributions (MSFT only)
      "hsa_ee": float,       # HSA Employee contributions (MSFT only)
      "fsa_dep_care": float, # FSA Dependent Care / DCFSA (MSFT & UoU)
      "fsa_limited_vision_dental": float,  # FSA Limited Purpose for vision/dental (MSFT only)
      "fsa_health": float,   # FSA Health (UoU only)
      "403b_tda": float,     # 403(b) TDA retirement contributions (UoU only)
      "bb_med_den_insurance": float  # BlueCross BlueShield Med/Den insurance (UoU only)
    }
  },
  
  "taxes": {
    "value": float,          # Total taxes withheld (negative)
    "details": {
      "federal": float,      # Federal Income Tax (MSFT & UoU)
      "ss": float,           # Social Security Tax (MSFT & UoU)
      "medicare": float,     # Medicare Tax (MSFT & UoU)
      "state": float         # State Withholding Tax (MSFT & UoU)
    }
  },
  
  "aftertax_deductions": {
    "value": float,          # Total after-tax deductions (negative, refunds positive)
    "details": {
      "401k": float,         # 401K After Tax contributions (MSFT only)
      "401k-roth": float,    # 401K Roth contributions (MSFT only)
      "espp": float,         # Employee Stock Purchase Plan (MSFT only)
      "espp_refund": float,  # ESPP refund when plan period ends (MSFT only)
      "add_insurance": float,       # AD&D Family Insurance (MSFT only)
      "life_dep_insurance": float,  # Dependent Life Insurance (MSFT & UoU)
      "life_emp_insurance": float,  # Life Employee Basic (UoU only)
      "giving_program": float       # Corporate Giving Program (MSFT only)
    }
  },
  
  "net_pay": {
    "value": float           # Net pay (take-home)
  },
  
  "stock_pay": {
    "value": float,          # MSFT only, 0 for UoU
    "details": {
      "income": float,       # Stock Award Income Offset (MSFT only)
      "tax": float           # Stock Award Taxes Offset (MSFT only)
    }
  },
  
  "validation": {
    "value": float           # Should be ~0 if parsing is correct
  }
}

Validation Invariants (all must pass for accurate parsing):
  1. Net Pay Balance:
     gross - net_pay - stock_pay - taxes - pretax - aftertax ≈ 0
     (stored in validation.value)

  2. Taxes Sum:
     taxes.value = sum(taxes.details.values())

  3. Pretax Deductions Sum:
     pretax_deductions.value = sum(pretax_deductions.details.values())

  4. Aftertax Deductions Sum:
     aftertax_deductions.value = sum(aftertax_deductions.details.values())

Run `python scripts/validate_paystub_parser_invariant.py` to verify all paystubs.
    (All deductions/taxes are negative values from PDF)
  
  Component Sums:
    gross.value = sum(gross.details.values())
    taxes.value = sum(taxes.details.values())

Microsoft Paystub Layout:
-------------------------
MSFT paystubs have a two-column layout with specific x-positions:

LEFT SIDE (x < 340):
  - Earnings (Base Salary, Stock Award Income, Perks+ Taxable, Reward Bonus)
  - Taxes (Federal Income Tax, Social Security Tax, Medicare Tax)
  - Benefits deductions (DCFSA, LPFSA, AD&D, Giving Program)
  - Current value column: x < 250
  - YTD value column: x >= 250 and x < 340

RIGHT SIDE (x >= 340):
  - Retirement deductions (401K Pre Tax, 401K After Tax, 401K Roth, HSA EE)
  - ESPP deductions
  - Stock Award Offsets (Income Offset, Taxes Offset)
  - Current value column: x ~ 441-475
  - YTD value column: x >= 500

Position-Aware Extraction:
--------------------------
Some fields require position-aware extraction using `_find_position_aware_values()`:

NEEDS POSITION-AWARE (left side, single-value ambiguity or right-side interference):
  - Federal Income Tax, Social Security Tax, Medicare Tax (may have only YTD when maxed)
  - Perks+ Taxable, Reward Bonus, Stock Award Income (may have only YTD)
  - ESPP Refund (right-side "Federal taxable wages" values can interfere)
  - Stock Award Income Offset, Stock Award Taxes Offset
  - Giving Program

DOES NOT NEED POSITION-AWARE:
  - DCFSA, LPFSA, AD&D - Always have both current and YTD values
  - 401K (Pre Tax, After Tax, Roth), HSA EE, ESPP - On right side, text-based
    extraction works with fallback logic: if only one value found, it's YTD
    and current is set to 0.0

University of Utah Paystub Layout:
----------------------------------
UoU paystubs use a summary line format:
  "Current [gross] [fed_taxable] [taxes] [deductions] [net_pay]"
Simpler layout, no position-aware extraction needed.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List
import pdfplumber
from backend.app.constants import EMPLOYER_MICROSOFT, EMPLOYER_U_OF_UTAH, EMPLOYER_UNKNOWN
import logging
from backend.app.services.pdf_utils import detect_employer, extract_pdf_text, extract_pdf_text_left_half
from backend.app.services.paths import repo_root


def _relpath(p: Path) -> str:
    try:
        return p.relative_to(repo_root()).as_posix()
    except Exception:
        return str(p)

logger = logging.getLogger(__name__)


def _extract_money_tokens(line: str) -> List[str]:
    """Return a list of money tokens found in a line of text."""
    # Match numbers with optional leading/trailing minus sign or parentheses
    # Examples: 862.14, 862.14-, -862.14, (862.14), 21,097.08-
    money_re = re.compile(r"(?<!\d)(?:\(?-?[\d,]+\.\d{2}-?\)?)(?!\d)")
    return money_re.findall(line)


def _to_float(s: str) -> Optional[float]:
    """Convert a money string to float, handling commas and parentheses."""
    try:
        s_clean = s.strip()
        neg = False
        if s_clean.startswith("(") and s_clean.endswith(")"):
            neg = True
            s_clean = s_clean[1:-1]
        if s_clean.endswith("-"):
            neg = True
            s_clean = s_clean[:-1]
        s_clean = s_clean.replace(",", "").replace("-", "")
        value = float(s_clean)
        return -value if neg else value
    except Exception:
        return None


def _find_row_values(lines: List[str], patterns: List[re.Pattern]) -> Tuple[Optional[float], Optional[float]]:
    """Search lines for pattern and return (current, ytd) values."""
    for line in lines:
        for pat in patterns:
            match = pat.search(line)
            if match:
                after_label = line[match.end():]
                tokens = _extract_money_tokens(after_label)
                if not tokens:
                    return None, None
                if len(tokens) >= 2:
                    return _to_float(tokens[0]), _to_float(tokens[1])
                else:
                    return _to_float(tokens[0]), None
    return None, None


def _find_earnings_values(lines: List[str], patterns: List[re.Pattern]) -> Tuple[Optional[float], Optional[float]]:
    """
    Search lines for earnings pattern and return (current, ytd) values.
    Earnings lines have format: [label] [rate] [current] [ytd]
    So we skip the first token (rate) and return tokens[1], tokens[2].
    """
    for line in lines:
        for pat in patterns:
            match = pat.search(line)
            if match:
                after_label = line[match.end():]
                tokens = _extract_money_tokens(after_label)
                if not tokens:
                    return None, None
                # Earnings format: rate, current, ytd - skip rate
                if len(tokens) >= 3:
                    return _to_float(tokens[1]), _to_float(tokens[2])
                elif len(tokens) >= 2:
                    # Might be current and ytd without rate
                    return _to_float(tokens[0]), _to_float(tokens[1])
                else:
                    return _to_float(tokens[0]), None
    return None, None


def _find_single_value(lines: List[str], patterns: List[re.Pattern]) -> Optional[float]:
    """Search lines for pattern and return the first value found."""
    val, _ = _find_row_values(lines, patterns)
    return val


def _find_stock_award_income(lines: List[str], pdf_path: Path = None) -> Tuple[Optional[float], Optional[float]]:
    """
    Extract Stock Award Income (current, ytd) from paystub.
    Uses position-aware extraction to correctly distinguish current vs YTD.
    
    Note: This is for "Stock Award Income" (earnings), NOT "Stock Award Income Offset" (deduction).
    """
    if pdf_path:
        # Use the generic position-aware function
        # Search for "Stock Award Income" but exclude lines with "Offset"
        import pdfplumber
        
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page in pdf.pages:
                chars = page.chars
                if not chars:
                    continue
                
                lines_dict: Dict[float, List[Tuple[float, str]]] = {}
                for char in chars:
                    if char.get('text'):
                        top = round(char['top'], 0)
                        if top not in lines_dict:
                            lines_dict[top] = []
                        lines_dict[top].append((char['x0'], char['text']))
                
                for top, char_list in sorted(lines_dict.items()):
                    char_list.sort(key=lambda x: x[0])
                    full_text = ''.join(c[1] for c in char_list)
                    
                    # Match "Stock Award Income" but NOT "Stock Award Income Offset"
                    if 'StockAwardIncome' in full_text.replace(' ', '') and 'Offset' not in full_text:
                        left_chars = [(x, t) for x, t in char_list if x < 340]
                        
                        num_chars = []
                        for x, t in left_chars:
                            if t in '0123456789.,-' and x > 120:
                                num_chars.append((x, t))
                        
                        if num_chars:
                            current_val_chars = []
                            ytd_val_chars = []
                            for x, t in num_chars:
                                if x < 250:
                                    current_val_chars.append(t)
                                else:
                                    ytd_val_chars.append(t)
                            
                            current_str = ''.join(current_val_chars).strip(',.-')
                            ytd_str = ''.join(ytd_val_chars).strip(',.-')
                            
                            current_val = _to_float(current_str) if current_str else 0.0
                            ytd_val = _to_float(ytd_str) if ytd_str else None
                            
                            return current_val, ytd_val
        
        return 0.0, None
    
    # Fallback to text-based extraction (legacy)
    return 0.0, None


def _find_espp_refund_values(pdf_path: Path) -> Tuple[Optional[float], Optional[float]]:
    """
    Extract ESPP Refund values using position-aware extraction.
    Delegates to _find_position_aware_values with appropriate parameters.
    """
    return _find_position_aware_values(pdf_path, "ESPP Refund", label_end_x=100)


def _find_perks_taxable_values(pdf_path: Path) -> Tuple[Optional[float], Optional[float]]:
    """
    Extract Perks+ Taxable values using position-aware extraction.
    Delegates to _find_position_aware_values with appropriate parameters.
    Note: PDF text may be "Perks+Taxable" or "Perks+ Taxable"
    """
    return _find_position_aware_values(pdf_path, "Perks+ Taxable", label_end_x=100)


def _find_reward_bonus_values(pdf_path: Path) -> Tuple[Optional[float], Optional[float]]:
    """
    Extract Reward Bonus values using position-aware extraction.
    Delegates to _find_position_aware_values with appropriate parameters.
    """
    return _find_position_aware_values(pdf_path, "Reward Bonus", label_end_x=100)


def _find_stock_offset_values(pdf_path: Path, offset_type: str = "income") -> Tuple[Optional[float], Optional[float]]:
    """
    Extract Stock Award Income/Taxes Offset values using position-aware extraction.
    Delegates to _find_position_aware_values with appropriate parameters.
    
    Args:
        pdf_path: Path to the PDF file
        offset_type: "income" for Stock Award Income Offset, "taxes" for Stock Award Taxes Offset
    """
    search_pattern = "Stock Award Income Offset" if offset_type == "income" else "Stock Award Taxes Offset"
    return _find_position_aware_values(pdf_path, search_pattern, label_end_x=150)


def _find_position_aware_values(pdf_path: Path, search_pattern: str, label_end_x: int = 130) -> Tuple[Optional[float], Optional[float]]:
    """
    Generic position-aware extraction for any field.
    
    MSFT paystubs have:
    - Current value column at x < 250
    - YTD value column at x >= 250 and x < 340
    - Right side (x >= 340) contains other data - ignore
    
    Args:
        pdf_path: Path to the PDF file
        search_pattern: Text pattern to search for (spaces will be removed for matching)
        label_end_x: X position where the label ends (values start after this)
    
    Returns:
        Tuple of (current_period_value, ytd_value)
    """
    import pdfplumber
    
    # Remove spaces from search pattern for matching
    search_term = search_pattern.replace(' ', '')
    
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            chars = page.chars
            if not chars:
                continue
            
            # Group characters by Y position (line)
            lines_dict: Dict[float, List[Tuple[float, str]]] = {}
            for char in chars:
                if char.get('text'):
                    top = round(char['top'], 0)
                    if top not in lines_dict:
                        lines_dict[top] = []
                    lines_dict[top].append((char['x0'], char['text']))
            
            # Find line containing the search pattern
            for top, char_list in sorted(lines_dict.items()):
                char_list.sort(key=lambda x: x[0])
                full_text = ''.join(c[1] for c in char_list)
                
                if search_term in full_text.replace(' ', ''):
                    # Filter to only characters from left side (x < 340)
                    left_chars = [(x, t) for x, t in char_list if x < 340]
                    
                    # Extract money values by position
                    num_chars = []
                    for x, t in left_chars:
                        if t in '0123456789.,-' and x > label_end_x:
                            num_chars.append((x, t))
                    
                    if num_chars:
                        current_val_chars = []
                        ytd_val_chars = []
                        for x, t in num_chars:
                            if x < 250:
                                current_val_chars.append(t)
                            else:
                                ytd_val_chars.append(t)
                        
                        current_str = ''.join(current_val_chars).strip(',.')
                        ytd_str = ''.join(ytd_val_chars).strip(',.')
                        
                        current_val = _to_float(current_str) if current_str else 0.0
                        ytd_val = _to_float(ytd_str) if ytd_str else None
                        
                        return current_val, ytd_val
    
    return None, None


def find_pay_date(text: str) -> Optional[str]:
    """Extract pay date in ISO format (YYYY-MM-DD) from paystub text."""
    patterns = [
        r"Advice\s+Date\s*:?\s*(\d{2}/\d{2}/\d{4})",
        r"Period\s+Beg/End\s*:?\s*\d{2}/\d{2}/\d{4}\s+(\d{2}/\d{2}/\d{4})",
        r"Check\s+Date\s*:?\s*(\d{2}/\d{2}/\d{4})",
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


def parse_paystub_msft(pdf_path: Path) -> Dict[str, Any]:
    """
    Parse Microsoft paystub and return structured format.
    
    Returns:
        {
          "pay_date": str,
          "employer_name": str,
          "gross": {"value": float, "details": {}},
          "pretax_deductions": {"value": float, "details": {"401k": float, "hsa_ee": float}},
          "taxes": {"value": float, "details": {"federal": float, "ss": float, "medicare": float, "state": float}},
          "aftertax_deductions": {"value": float, "details": {"401k_aftertax": float, "401k_roth": float}},
          "net_pay": {"value": float},
          "stock_pay": {"value": float, "details": {"income": float, "tax": float}},
          "validation": {"value": float}
        }
    """
    # Extract text from PDF
    all_text = ""
    lines: List[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            all_text += page_text + "\n"
            lines.extend(page_text.splitlines())

    lines = [l.strip() for l in lines if l.strip()]

    # Define patterns for each field
    gross_patterns = [re.compile(r"\b(TOTAL\s+EARNINGS|GROSS\s+PAY)\b", re.IGNORECASE)]
    net_patterns = [re.compile(r"\bNET\s+PAY\b", re.IGNORECASE)]
    
    # Gross breakdown patterns
    base_salary_patterns = [re.compile(r"\bBase\s+Salary\b", re.IGNORECASE)]
    # Stock Award Income (NOT offset) - appears in earnings section
    stock_award_income_patterns = [re.compile(r"\bStock\s+Award\s+Income\b(?!\s+Offset)", re.IGNORECASE)]
    # Perks+ Taxable - taxable perks/benefits income
    perks_taxable_patterns = [re.compile(r"\bPerks\+?\s+Taxable\b", re.IGNORECASE)]
    # Reward Bonus - bonus income
    reward_bonus_patterns = [re.compile(r"\bReward\s+Bonus\b", re.IGNORECASE)]
    # Vacation PO - vacation payout (rare, appears in some paystubs)
    vacation_po_patterns = [re.compile(r"\bVacation\s+PO\b", re.IGNORECASE)]
    # Shared Success Bonus - company-wide bonus (rare, appears in some paystubs)
    shared_success_bonus_patterns = [re.compile(r"\bShared\s+Success\s+Bonus\b", re.IGNORECASE)]
    
    # Tax patterns
    federal_patterns = [re.compile(r"\bFEDERAL\s+INCOME\s+TAX\b", re.IGNORECASE)]
    ss_patterns = [re.compile(r"\bSOCIAL\s+SECURITY\s+TAX\b", re.IGNORECASE)]
    medicare_patterns = [re.compile(r"\bMEDICARE\s+TAX\b", re.IGNORECASE)]
    state_patterns = [
        re.compile(r"\bWITHHOLDING\s*-\s*[A-Z]{2,}\b", re.IGNORECASE),
        re.compile(r"\b[A-Z]{2}\s+W/H\s+TAX\b", re.IGNORECASE),
        re.compile(r"\bSTATE\s+TAX\b", re.IGNORECASE),
    ]
    total_taxes_patterns = [re.compile(r"\bTOTAL\s+TAXES\b", re.IGNORECASE)]
    
    # Pre-tax deductions (401K Pre Tax + HSA EE)
    pretax_401k_patterns = [re.compile(r"\*?401K\s+Pre\s+Tax\b", re.IGNORECASE)]
    hsa_ee_patterns = [re.compile(r"\*?HSA\s+EE\s+Contribution\b", re.IGNORECASE)]
    total_retirement_patterns = [re.compile(r"\bTOTAL\s+RETIREMENT\b", re.IGNORECASE)]
    
    # After-tax deductions (401K After Tax + 401K Roth + ESPP + DCFSA + LPFSA + AD&D + Giving Program)
    aftertax_401k_patterns = [re.compile(r"\b401K\s+After\s+Tax\b", re.IGNORECASE)]
    roth_401k_patterns = [re.compile(r"\b401K\s+Roth\b", re.IGNORECASE)]
    # ESPP line starts with "ESPP" - excludes "ESPP Disq Disp" and "ESPP Refund" which appear mid-line
    espp_patterns = [re.compile(r"^\s*ESPP\b(?!\s+Disq)(?!\s+Refund)", re.IGNORECASE)]
    # Note: ESPP Refund uses position-aware extraction via _find_espp_refund_values()
    dcfsa_patterns = [re.compile(r"\*?DCFSA\s+Deduction\b", re.IGNORECASE)]
    lpfsa_patterns = [re.compile(r"\*?LPFSA\s+Deduction\b", re.IGNORECASE)]
    add_patterns = [re.compile(r"\bAD&D\s+Family\s+Ins\b", re.IGNORECASE)]
    dep_life_patterns = [re.compile(r"\bDependent\s+Life\s+Ins\b", re.IGNORECASE)]
    # Note: Giving Program uses position-aware extraction via _find_position_aware_values()
    
    # Stock award patterns (from "Other" section)
    stock_income_patterns = [re.compile(r"\bStock\s+Award\s+Income\s+Offset\b", re.IGNORECASE)]
    stock_taxes_patterns = [re.compile(r"\bStock\s+Award\s+Taxes\s+Offset\b", re.IGNORECASE)]
    
    # Total benefits and other
    total_benefits_patterns = [re.compile(r"\bTOTAL\s+BENEFITS\b", re.IGNORECASE)]
    total_other_patterns = [re.compile(r"\bTOTAL\s+OTHER\b", re.IGNORECASE)]
    
    # Extract values
    gross, ytd_gross = _find_row_values(lines, gross_patterns)
    net_pay, ytd_net = _find_row_values(lines, net_patterns)
    
    # Gross breakdown - use _find_earnings_values to skip rate column
    base_salary, base_salary_ytd = _find_earnings_values(lines, base_salary_patterns)
    # Stock Award Income - use position-aware extraction to avoid misreading YTD as current
    stock_award_income, stock_award_income_ytd = _find_stock_award_income(lines, pdf_path)
    # Perks+ Taxable - use position-aware extraction to avoid misreading YTD as current
    perks_taxable, perks_taxable_ytd = _find_perks_taxable_values(pdf_path)
    # Reward Bonus - use position-aware extraction to avoid misreading YTD as current
    reward_bonus, reward_bonus_ytd = _find_reward_bonus_values(pdf_path)
    # Vacation PO - use position-aware extraction, skip rate column (x < 180)
    vacation_po, vacation_po_ytd = _find_position_aware_values(pdf_path, "Vacation PO", label_end_x=180)
    # Shared Success Bonus - use position-aware extraction
    shared_success_bonus, shared_success_bonus_ytd = _find_position_aware_values(pdf_path, "Shared Success Bonus")
    
    # Taxes - use position-aware extraction to handle cases where only YTD exists
    # (e.g., SS tax when annual maximum is reached - only YTD at x>=250, current is 0)
    # Note: Labels in MSFT paystubs are "FederalIncomeTax", "SocialSecurityTax", "MedicareTax"
    federal, ytd_federal = _find_position_aware_values(pdf_path, "Federal Income Tax")
    ss, ytd_ss = _find_position_aware_values(pdf_path, "Social Security Tax")
    medicare, ytd_medicare = _find_position_aware_values(pdf_path, "Medicare Tax")
    state, ytd_state = _find_position_aware_values(pdf_path, "UT W/H Tax")
    total_taxes, _ = _find_row_values(lines, total_taxes_patterns)
    
    # Pre-tax deductions - MSFT paystubs may have:
    # - "*401K Pre Tax X.XX- Y.YY-" (current and YTD)
    # - "*401K Pre Tax Y.YY-" (YTD only, no current contribution)
    # We need to check if there are two values to distinguish current vs YTD
    pretax_401k, pretax_401k_ytd = _find_row_values(lines, pretax_401k_patterns)
    hsa_ee, hsa_ee_ytd = _find_row_values(lines, hsa_ee_patterns)
    total_retirement, total_retirement_ytd = _find_row_values(lines, total_retirement_patterns)
    
    # If pretax_401k has a value but pretax_401k_ytd is None, it means only YTD was captured
    # In this case, current period pretax 401k is 0 (no contribution this period)
    if pretax_401k is not None and pretax_401k_ytd is None:
        # The single value captured is YTD, not current
        pretax_401k_ytd = pretax_401k
        pretax_401k = 0.0
    
    # Same for HSA EE
    if hsa_ee is not None and hsa_ee_ytd is None:
        hsa_ee_ytd = hsa_ee
        hsa_ee = 0.0
    
    # After-tax deductions  
    aftertax_401k, aftertax_401k_ytd = _find_row_values(lines, aftertax_401k_patterns)
    roth_401k, roth_401k_ytd = _find_row_values(lines, roth_401k_patterns)
    espp, espp_ytd = _find_row_values(lines, espp_patterns)
    # Use position-aware extraction for ESPP Refund to avoid interference from
    # right-side "Federal taxable wages" values on the same line
    espp_refund, espp_refund_ytd = _find_espp_refund_values(pdf_path)
    dcfsa, dcfsa_ytd = _find_row_values(lines, dcfsa_patterns)
    lpfsa, lpfsa_ytd = _find_row_values(lines, lpfsa_patterns)
    add_ins, add_ins_ytd = _find_row_values(lines, add_patterns)
    life_dep_ins, life_dep_ins_ytd = _find_row_values(lines, dep_life_patterns)
    # Giving Program - use position-aware extraction
    giving_program, giving_program_ytd = _find_position_aware_values(pdf_path, "Giving Program")
    
    # Same logic for after-tax
    if aftertax_401k is not None and aftertax_401k_ytd is None:
        aftertax_401k_ytd = aftertax_401k
        aftertax_401k = 0.0
    if roth_401k is not None and roth_401k_ytd is None:
        roth_401k_ytd = roth_401k
        roth_401k = 0.0
    if espp is not None and espp_ytd is None:
        espp_ytd = espp
        espp = 0.0
    # Note: espp_refund already handled by _find_espp_refund_values which returns
    # (0.0, ytd) when only one value is found
    if dcfsa is not None and dcfsa_ytd is None:
        dcfsa_ytd = dcfsa
        dcfsa = 0.0
    if lpfsa is not None and lpfsa_ytd is None:
        lpfsa_ytd = lpfsa
        lpfsa = 0.0
    if add_ins is not None and add_ins_ytd is None:
        add_ins_ytd = add_ins
        add_ins = 0.0
    if life_dep_ins is not None and life_dep_ins_ytd is None:
        life_dep_ins_ytd = life_dep_ins
        life_dep_ins = 0.0
    
    # Stock awards - use position-aware extraction to avoid right-side interference
    stock_income, stock_income_ytd = _find_stock_offset_values(pdf_path, "income")
    stock_taxes, stock_taxes_ytd = _find_stock_offset_values(pdf_path, "taxes")
    
    # Total benefits and other
    total_benefits, _ = _find_row_values(lines, total_benefits_patterns)
    total_other, _ = _find_row_values(lines, total_other_patterns)
    
    # Convert negative values to positive for deductions (they're stored as negative in paystub)
    def abs_val(v: Optional[float]) -> Optional[float]:
        return abs(v) if v is not None else None
    
    # Build structured result
    # Pre-tax = 401K Pre Tax + HSA EE + DCFSA + LPFSA - honor signs from PDF (negative = deduction)
    pretax_401k_val = pretax_401k if pretax_401k is not None else 0.0
    hsa_ee_val = hsa_ee if hsa_ee is not None else 0.0
    fsa_dep_care_val = dcfsa if dcfsa is not None else 0.0
    fsa_limited_vision_dental_val = lpfsa if lpfsa is not None else 0.0
    
    # Store pretax details - honor signs directly from PDF
    pretax_details = {
        "401k": pretax_401k_val,
        "hsa_ee": hsa_ee_val,
        "fsa_dep_care": fsa_dep_care_val,
        "fsa_limited_vision_dental": fsa_limited_vision_dental_val
    }
    # pretax_total = sum of all details (should be negative from PDF)
    pretax_total = sum(pretax_details.values())
    
    # After-tax = 401K After Tax + 401K Roth + ESPP + AD&D + Giving Program
    # Honor signs directly from PDF (negative = deduction, positive = refund)
    aftertax_401k_val = aftertax_401k if aftertax_401k is not None else 0.0
    roth_401k_val = roth_401k if roth_401k is not None else 0.0
    espp_val = espp if espp is not None else 0.0
    espp_refund_val = espp_refund if espp_refund is not None else 0.0
    add_insurance_val = add_ins if add_ins is not None else 0.0
    life_dep_insurance_val = life_dep_ins if life_dep_ins is not None else 0.0
    giving_program_val = giving_program if giving_program is not None else 0.0
    
    # Store details - honor signs directly from PDF
    aftertax_details = {
        "401k": aftertax_401k_val,
        "401k-roth": roth_401k_val,
        "espp": espp_val,
        "espp_refund": espp_refund_val,
        "add_insurance": add_insurance_val,
        "life_dep_insurance": life_dep_insurance_val,
        "giving_program": giving_program_val
    }
    # aftertax_total = sum of all details (should be negative from PDF, refunds positive)
    aftertax_total = sum(aftertax_details.values())

    
    # Taxes - honor signs from PDF
    federal_val = federal if federal is not None else 0.0
    ss_val = ss if ss is not None else 0.0
    medicare_val = medicare if medicare is not None else 0.0
    state_val = state if state is not None else 0.0
    
    taxes_details = {
        "federal": federal_val,
        "ss": ss_val,
        "medicare": medicare_val,
        "state": state_val
    }
    taxes_total = sum(taxes_details.values())
    
    # Use Total Taxes from paystub if available (more accurate)
    if total_taxes is not None:
        taxes_total = total_taxes
    
    # Stock Award Income Offset (negative) 
    # Stock Award Taxes Offset (positive) 
    # Those two show as Offset so needs to adjust the signs accordingly
    stock_income_val = abs_val(stock_income) if stock_income else 0.0
    stock_taxes_val = -abs_val(stock_taxes) if stock_taxes else 0.0
    stock_details = {
        "income": stock_income_val,
        "tax": stock_taxes_val
    }
    stock_pay = stock_income_val + stock_taxes_val # (since tax is negative)
    
    # Gross and Net
    gross_val = gross
    net_pay_val = net_pay
    
    # Validation: gross - net + pretax + taxes + aftertax = ~0
    # All values honor signs from PDF: deductions/taxes are negative
    net_pay_diff = None
    if gross_val and net_pay_val:
        net_pay_diff = round(gross_val - net_pay_val - stock_pay + pretax_total + taxes_total + aftertax_total, 2)
    
    # Calculate sum diffs for detailed validation
    tax_sum_diff = round(taxes_total - sum(taxes_details.values()), 2) if taxes_total else None
    pretax_sum_diff = round(pretax_total - sum(pretax_details.values()), 2)
    aftertax_sum_diff = round(aftertax_total - sum(aftertax_details.values()), 2)
    
    # Gross breakdown values
    base_salary_val = base_salary if base_salary else 0.0
    stock_award_income_val = stock_award_income if stock_award_income else 0.0
    perks_taxable_val = perks_taxable if perks_taxable else 0.0
    reward_bonus_val = reward_bonus if reward_bonus else 0.0
    vacation_po_val = vacation_po if vacation_po else 0.0
    shared_success_bonus_val = shared_success_bonus if shared_success_bonus else 0.0
    
    result = {
        "pay_date": find_pay_date(all_text),
        "employer_name": EMPLOYER_MICROSOFT,
        "gross": {
            "value": gross_val,
            "details": {
                "base": base_salary_val,
                "stock": stock_award_income_val,
                "perks": perks_taxable_val,
                "bonus": reward_bonus_val,
                "vacation_po": vacation_po_val,
                "shared_success_bonus": shared_success_bonus_val
            }
        },
        "pretax_deductions": {
            "value": round(pretax_total, 2),
            "details": pretax_details
        },
        "taxes": {
            "value": round(taxes_total, 2) if taxes_total else None,
            "details": taxes_details
        },
        "aftertax_deductions": {
            "value": round(aftertax_total, 2),
            "details": aftertax_details
        },
        "net_pay": {
            "value": net_pay_val
        },
        "stock_pay": {
            "value": round(stock_pay, 2),
            "details": stock_details if stock_details else {}
        },
        "validation": {
            "net_pay_diff": net_pay_diff,
            "tax_sum_diff": tax_sum_diff,
            "pretax_sum_diff": pretax_sum_diff,
            "aftertax_sum_diff": aftertax_sum_diff
        },
        # Additional metadata
        "ytd": {
            "gross": ytd_gross,
            "net_pay": ytd_net,
            "federal_tax": ytd_federal,
            "state_tax": ytd_state,
            "ss_tax": ytd_ss,
            "medicare_tax": ytd_medicare,
        },
        # Raw extracted values for debugging
        "_raw": {
            "total_retirement": total_retirement,
            "total_benefits": total_benefits,
            "total_other": total_other,
            "total_taxes": total_taxes,
        },
        "warnings": [],
        "source_pdf": _relpath(pdf_path),
        "parser": "msft",
    }
    
    # Validation checks
    if result["gross"]["value"] is not None and result["gross"]["value"] < 300:
        result["warnings"].append(f"gross_pay looked too small ({result['gross']['value']}); likely a rate")
    
    return result


def parse_university_paystub(pdf_path: Path, employer_name: str = "unknown") -> Dict[str, Any]:
    """
    Parse University of Utah paystub and return structured format.
    
    For non-MSFT paystubs, we extract totals directly where available.
    UoU format has a summary line like:
    "Current 6,771.38 6,637.46 1,596.72 134.65 5,040.01"
    which corresponds to: TOTAL GROSS, FED TAXABLE GROSS, TOTAL TAXES, TOTAL DEDUCTIONS, NET PAY
    """
    def _to_float_money(s: str) -> float:
        """Convert a money string to float, removing commas and dollar signs."""
        return float(s.replace(",", "").replace("$", "").strip())

    def _find_value_by_label(text: str, label_patterns: List[str], want_ytd: bool = False) -> Optional[float]:
        """Search for a label pattern and extract the associated value."""
        lines = text.splitlines()
        
        for i, line in enumerate(lines):
            for pat in label_patterns:
                match = re.search(pat, line, re.IGNORECASE)
                if match:
                    after_label = line[match.end():]
                    nums = re.findall(r"[\d,]+\.\d{2}", after_label)
                    
                    if not nums:
                        nums = re.findall(r"[\d,]+\.\d{2}", line)
                    
                    if nums and len(nums) >= 2:
                        try:
                            if want_ytd:
                                return _to_float_money(nums[-1])
                            else:
                                return _to_float_money(nums[0])
                        except Exception:
                            pass
                    elif nums and len(nums) == 1:
                        if not want_ytd:
                            try:
                                return _to_float_money(nums[0])
                            except Exception:
                                pass
        return None

    def _find_pay_date_generic(text: str) -> Optional[str]:
        """Extract pay date from generic paystub text."""
        patterns = [
            r"Check\s+Date[:\s]*(\d{1,2}/\d{1,2}/\d{4})",
            r"Pay\s+Date[:\s]*(\d{1,2}/\d{1,2}/\d{4})",
            r"Period\s+End(?:ing)?[:\s]*(\d{1,2}/\d{1,2}/\d{4})",
            r"Advice\s+Date[:\s]*(\d{1,2}/\d{1,2}/\d{4})",
        ]
        
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                date_str = m.group(1).strip()
                for fmt in ("%m/%d/%Y", "%m/%d/%y"):
                    try:
                        dt = datetime.strptime(date_str, fmt)
                        return dt.strftime("%Y-%m-%d")
                    except ValueError:
                        continue
        return None
    
    def _parse_uou_summary_line(text: str) -> Dict[str, Optional[float]]:
        """
        Parse UoU summary line format:
        "Current 6,771.38 6,637.46 1,596.72 134.65 5,040.01"
        Returns: {gross, fed_taxable, total_taxes, total_deductions, net_pay}
        """
        result = {"gross": None, "fed_taxable": None, "total_taxes": None, 
                  "total_deductions": None, "net_pay": None}
        
        # Look for "Current" line with 5 numbers
        for line in text.splitlines():
            if re.match(r"^\s*Current\s+[\d,]+\.\d{2}", line):
                nums = re.findall(r"[\d,]+\.\d{2}", line)
                if len(nums) >= 5:
                    result["gross"] = _to_float_money(nums[0])
                    result["fed_taxable"] = _to_float_money(nums[1])
                    result["total_taxes"] = _to_float_money(nums[2])
                    result["total_deductions"] = _to_float_money(nums[3])
                    result["net_pay"] = _to_float_money(nums[4])
                    break
        return result
    
    def _parse_uou_deductions(text: str) -> Dict[str, Any]:
        """
        Parse UoU before-tax and after-tax deductions.
        Returns: {pretax: {details}, aftertax: {details}, pretax_total: float, aftertax_total: float}
        """
        pretax = {}
        aftertax = {}
        pretax_total = None
        aftertax_total = None
        
        # Parse individual deduction items
        # Before-tax patterns (Current value is first number after description)
        pretax_patterns = [
            (r"BlueCross\s+BlueShield\s+Med/Den\s+([\d,]+\.\d{2})", "bb_med_den_insurance"),
            (r"403\(b\)\s+TDA\s+([\d,]+\.\d{2})", "403b_tda"),
            (r"FSA\s+Health\s+([\d,]+\.\d{2})", "fsa_health"),
            (r"FSA\s+Dependent\s+([\d,]+\.\d{2})", "fsa_dep_care"),
        ]
        
        # After-tax patterns
        # Note: UoU PDF text can be mangled - patterns vary by year
        # 2024: "Life Plan 2 Child", 2025+: "Life Child Additional"
        aftertax_patterns = [
            (r"Life\s+(?:Plan\s+2\s+)?Child(?:\s+Additional)?\s+([\d,]+\.\d{2})", "life_dep_insurance"),
            (r"(?:Basic\s+)?(?:Employee\s+)?Life(?:\s+Employee)?(?:\s+Basic)?\s+([\d,]+\.\d{2})", "life_emp_insurance"),
        ]
        
        for pat, key in pretax_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                pretax[key] = _to_float_money(m.group(1))
        
        for pat, key in aftertax_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                aftertax[key] = _to_float_money(m.group(1))
        
        # Find the line with "TOTAL: X YTD TOTAL: Y YTD *TAXABLE" pattern
        # This is the deductions summary row
        # Pattern: "TOTAL: 149.90 2,709.39 TOTAL: 0.73 13.14 *TAXABLE"
        for line in text.splitlines():
            # The deductions TOTAL row ends with *TAXABLE
            if line.count("TOTAL:") >= 2 and "*TAXABLE" in line:
                totals = re.findall(r"TOTAL:\s*([\d,]+\.\d{2})", line)
                if len(totals) >= 2:
                    pretax_total = _to_float_money(totals[0])
                    aftertax_total = _to_float_money(totals[1])
                    break
        
        return {
            "pretax": pretax, 
            "aftertax": aftertax,
            "pretax_total": pretax_total,
            "aftertax_total": aftertax_total
        }

    # Extract text from PDF
    text = extract_pdf_text(pdf_path, max_pages=2)
    
    # Try UoU summary line format first
    uou_summary = _parse_uou_summary_line(text)
    uou_deductions = _parse_uou_deductions(text)
    
    gross = uou_summary["gross"]
    net_pay = uou_summary["net_pay"]
    total_deductions = uou_summary["total_deductions"]
    
    # If UoU format didn't work, fall back to generic extraction
    if gross is None:
        gross = _find_value_by_label(text, [
            r"\bGROSS\s+PAY\b", r"\bTOTAL\s+GROSS\b",
            r"\bGROSS\s+EARNINGS\b", r"\bTOTAL\s+EARNINGS\b",
        ])
    
    if net_pay is None:
        net_pay = _find_value_by_label(text, [
            r"\bNET\s+PAY\b", r"\bTAKE\s+HOME\b",
        ])
    
    # Taxes
    federal = _find_value_by_label(text, [
        r"\bFed\s+Withhold(?:ng)?\b",
        r"\bFED(?:ERAL)?\s+WITHHOLD(?:I?NG)?\b",
        r"\bFEDERAL\s+(?:INCOME\s+)?TAX\b",
    ])
    state = _find_value_by_label(text, [
        r"\bUT\s+Withhold(?:ng)?\b",
        r"\b[A-Z]{2}\s+WITHHOLD(?:I?NG)?\b",
        r"\bSTATE\s+(?:INCOME\s+)?TAX\b",
    ])
    ss = _find_value_by_label(text, [
        r"\bFed\s+OASDI/?EE\b",
        r"\bSOCIAL\s+SECURITY\b",
    ])
    medicare = _find_value_by_label(text, [
        r"\bFed\s+MED/?EE\b",
        r"\bFED\s+MED(?:ICARE)?/?EE\b",
        r"\bMEDICARE\b",
    ])
    
    # Build taxes dict
    taxes_total = 0.0
    taxes_details = {}
    if federal:
        taxes_total += federal
        taxes_details["federal"] = federal
    if ss:
        taxes_total += ss
        taxes_details["ss"] = ss
    if medicare:
        taxes_total += medicare
        taxes_details["medicare"] = medicare
    if state:
        taxes_total += state
        taxes_details["state"] = state
    
    # Use UoU total taxes if available and our sum doesn't match
    if uou_summary["total_taxes"] and abs(taxes_total - uou_summary["total_taxes"]) > 1:
        taxes_total = uou_summary["total_taxes"]
    
    # For UoU, use the parsed TOTAL: rows for pretax and aftertax
    # Also use the parsed individual deduction details
    if uou_deductions["pretax_total"] is not None:
        pretax_total = uou_deductions["pretax_total"]
        aftertax_total = uou_deductions["aftertax_total"] or 0.0
        pretax_details = uou_deductions["pretax"]  # Now contains parsed individual items
        aftertax_details = uou_deductions["aftertax"]  # Now contains parsed individual items
    elif total_deductions is not None:
        # Fallback: use combined total_deductions from summary
        pretax_total = total_deductions
        aftertax_total = 0.0
        pretax_details = uou_deductions["pretax"]
        aftertax_details = uou_deductions["aftertax"]
    else:
        # Fallback for non-UoU generic paystubs
        pretax_total = sum(uou_deductions["pretax"].values()) if uou_deductions["pretax"] else None
        aftertax_total = sum(uou_deductions["aftertax"].values()) if uou_deductions["aftertax"] else None
        pretax_details = uou_deductions["pretax"]
        aftertax_details = uou_deductions["aftertax"]
    
    # For gross, add details (university usually only has base pay)
    gross_details = {"base": gross} if gross else {}
    
    # Validation: gross - net - taxes - total_deductions = ~0
    net_pay_diff = None
    if gross and net_pay:
        deductions = (pretax_total or 0) + (aftertax_total or 0)
        net_pay_diff = round(gross - net_pay - taxes_total - deductions, 2)
    
    # Calculate sum diffs for detailed validation
    tax_sum_diff = round(taxes_total - sum(taxes_details.values()), 2) if taxes_total else None
    pretax_sum_diff = round((pretax_total or 0) - sum(pretax_details.values()), 2)
    aftertax_sum_diff = round((aftertax_total or 0) - sum(aftertax_details.values()), 2)
    
    result = {
        "pay_date": _find_pay_date_generic(text),
        "employer_name": employer_name,
        "gross": {
            "value": gross,
            "details": gross_details
        },
        "pretax_deductions": {
            "value": pretax_total,
            "details": pretax_details
        },
        "taxes": {
            "value": round(taxes_total, 2) if taxes_total else None,
            "details": taxes_details
        },
        "aftertax_deductions": {
            "value": aftertax_total,
            "details": aftertax_details
        },
        "net_pay": {
            "value": net_pay
        },
        "stock_pay": {
            "value": 0,
            "details": {}
        },
        "validation": {
            "net_pay_diff": net_pay_diff,
            "tax_sum_diff": tax_sum_diff,
            "pretax_sum_diff": pretax_sum_diff,
            "aftertax_sum_diff": aftertax_sum_diff
        },
        "_raw": {
            "total_deductions": total_deductions,
        },
        "warnings": [],
        "source_pdf": _relpath(pdf_path),
        "parser": "university",
    }
    
    return result


def parse_paystub(pdf_path: Path, employee: str = None) -> Dict[str, Any]:
    """
    Parse a paystub and return the structured format.
    
    Args:
        pdf_path: Path to the PDF file to parse.
        employee: Expected employer name for validation.
    
    Returns:
        Structured dictionary with gross, pretax_deductions, taxes, 
        aftertax_deductions, net_pay, stock_pay, and validation.
    """
    logger.info(f"parse_paystub: pdf_path={pdf_path}, employee={employee}")
    pdf_path = Path(pdf_path)

    # Detect employer
    emp = detect_employer(str(pdf_path))
    if emp == EMPLOYER_UNKNOWN:
        text = extract_pdf_text(pdf_path, max_pages=2)
        emp = detect_employer(text)
    
    try:
        if emp == EMPLOYER_MICROSOFT:
            res = parse_paystub_msft(pdf_path)
        else:
            res = parse_university_paystub(pdf_path, employer_name=emp)
        
        if employee and emp != employee:
            res["warnings"].append(f"Detected employer '{emp}' does not match expected '{employee}'")
            
    except Exception as e:
        logger.error(f"Parser failed for {pdf_path.name}: {e}")
        res = {
            "pay_date": None,
            "employer_name": emp,
            "gross": {"value": None, "details": {}},
            "pretax_deductions": {"value": None, "details": {}},
            "taxes": {"value": None, "details": {}},
            "aftertax_deductions": {"value": None, "details": {}},
            "net_pay": {"value": None},
            "stock_pay": {"value": None, "details": {}},
            "validation": {
                "net_pay_diff": None,
                "tax_sum_diff": None,
                "pretax_sum_diff": None,
                "aftertax_sum_diff": None
            },
            "warnings": [f"Parser failed: {e}"],
            "source_pdf": _relpath(pdf_path),
            "parser": "error",
        }
    
    logger.info(f"Parsed paystub: {res}")
    return res