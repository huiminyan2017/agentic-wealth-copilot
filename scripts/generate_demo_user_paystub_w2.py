#!/usr/bin/env python3
"""
Generate all demo user paystub and W-2 PDFs, then re-derive groundtruth JSONs
by running the real parsers.

  DemoMicrosoftEmployee — 2 ADP-style paystubs (2018-04-15, 2018-09-13)
                        — 1 W-2 (tax year 2018)
  DemoUofUEmployee      — 1 UofU-style paystub (2024-04-30)
                        — 1 W-2 (tax year 2024)

DISCLAIMER: All employee names, addresses, IDs, wages, and financial figures
are entirely fictitious and generated for demo/testing purposes only.
Do NOT use as a template for tax or payroll documents.

Usage:
    cd <project-root>
    python scripts/generate_demo_user_paystub_w2.py
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

W, H = letter  # 612 × 792 pts

FONT_REG  = "Helvetica"
FONT_BOLD = "Helvetica-Bold"
FONT_MONO = "Courier"

SZ    = 8
SZ_SM = 7


# =============================================================================
# Shared helpers
# =============================================================================

def _m(v: float) -> str:
    """Money string with commas: 1,234,567.89"""
    return f"{v:,.2f}"

def draw(c, x, y, text, font=FONT_REG, sz=SZ):
    c.setFont(font, sz)
    c.drawString(x, y, text)

def hline(c, y, x0=36, x1=576):
    c.setStrokeColorRGB(0.6, 0.6, 0.6)
    c.line(x0, y, x1, y)
    c.setStrokeColorRGB(0, 0, 0)

def generate_single_page_pdf(out_path: Path, draw_fn, data: dict):
    c = canvas.Canvas(str(out_path), pagesize=letter)
    draw_fn(c, data)
    c.showPage()
    c.save()
    print(f"  PDF  → {out_path.name}")

def generate_paystub_groundtruth(pdf_path: Path, truth_path: Path, disclaimer: str):
    from backend.app.services.paystub_parser import parse_paystub
    result = parse_paystub(pdf_path)
    result["_disclaimer"] = disclaimer
    with open(truth_path, "w") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"  JSON → {truth_path.name}")

def generate_w2_groundtruth(pdf_path: Path, truth_path: Path,
                             employer: str, person: str, sha8: str, disclaimer: str):
    from backend.app.services.w2_parser import parse_w2
    result = parse_w2(pdf_path, employer=employer, person=person, sha8=sha8)
    result_dict = result.model_dump()
    result_dict["_disclaimer"] = disclaimer
    result_dict.pop("extracted_text_path", None)
    result_dict.pop("source_pdf_relpath", None)
    result_dict.pop("notes", None)
    with open(truth_path, "w") as f:
        json.dump(result_dict, f, indent=2, default=str)
    print(f"  JSON → {truth_path.name}")


# =============================================================================
# W-2 PDF layout  (shared by all employers)
# =============================================================================
#
# pdfplumber.extract_text() merges all drawString calls at the SAME y into one
# line. Strategy: draw label pairs at the same y, values at y-lh.
#
# d must contain:
#   year, ein, ssn, emp_name, emp_addr1, emp_addr2
#   er_name, er_addr1, er_addr2, er_state_id, state
#   wages, federal_tax, ss_wages, ss_tax, medicare_wages, medicare_tax
#   state_wages, state_tax
#   box12_entries: list of (slot_label, value, description)
#     e.g. [("12a  C", 516.00, "Taxable group-term life ins."), ...]
#   box14_entries: optional list of (label, value)  e.g. [("ESPP", 115470.00)]
#   disclaimer: per-employer disclaimer string

LH_W2 = 12

def draw_w2(c, d):
    y = H - 36

    draw(c, 36,  y, f"W-2  Wage and Tax Statement  {d['year']}", FONT_BOLD, 11)
    draw(c, 420, y, "Department of the Treasury — IRS", sz=SZ_SM)
    y -= LH_W2
    draw(c, 36,  y, d['disclaimer'], sz=SZ_SM)
    y -= LH_W2 * 1.5
    hline(c, y)
    y -= LH_W2 * 1.5

    draw(c, 36,  y, f"b  Employer identification number (EIN)    {d['ein']}", sz=SZ)
    draw(c, 310, y, f"a  Employee's social security number  {d['ssn']}", sz=SZ)
    y -= LH_W2
    draw(c, 36,  y, "c  Employer's name, address, and ZIP code", sz=SZ)
    y -= LH_W2
    draw(c, 36,  y, d['er_name'],  FONT_BOLD, SZ)
    y -= LH_W2
    draw(c, 36,  y, d['er_addr1'], sz=SZ)
    y -= LH_W2
    draw(c, 36,  y, d['er_addr2'], sz=SZ)
    y -= LH_W2
    draw(c, 36,  y, f"e  Employee's name   {d['emp_name']}", sz=SZ)
    y -= LH_W2
    draw(c, 36,  y, f"f  Employee's address   {d['emp_addr1']},  {d['emp_addr2']}", sz=SZ)
    y -= LH_W2 * 1.5
    hline(c, y)
    y -= LH_W2 * 1.5

    # Boxes 1/2 — labels on same y → one extracted line; values on next y
    draw(c, 36,  y, "1  Wages, tips, other comp.",    sz=SZ)
    draw(c, 310, y, "2  Federal income tax withheld", sz=SZ)
    y -= LH_W2
    draw(c, 36,  y, _m(d['wages']),       FONT_MONO, SZ)
    draw(c, 310, y, _m(d['federal_tax']), FONT_MONO, SZ)
    y -= LH_W2 * 1.5

    # Boxes 3/4
    draw(c, 36,  y, "3  Social security wages",        sz=SZ)
    draw(c, 310, y, "4  Social security tax withheld", sz=SZ)
    y -= LH_W2
    draw(c, 36,  y, _m(d['ss_wages']), FONT_MONO, SZ)
    draw(c, 310, y, _m(d['ss_tax']),   FONT_MONO, SZ)
    y -= LH_W2 * 1.5

    # Boxes 5/6
    draw(c, 36,  y, "5  Medicare wages and tips", sz=SZ)
    draw(c, 310, y, "6  Medicare tax withheld",   sz=SZ)
    y -= LH_W2
    draw(c, 36,  y, _m(d['medicare_wages']), FONT_MONO, SZ)
    draw(c, 310, y, _m(d['medicare_tax']),   FONT_MONO, SZ)
    y -= LH_W2 * 1.5
    hline(c, y)
    y -= LH_W2 * 1.5

    # Box 12 — variable number of entries per employer
    draw(c, 36, y, "Box 12 — Codes", FONT_BOLD, SZ)
    y -= LH_W2
    for slot_label, value, description in d['box12_entries']:
        draw(c, 36,  y, f"{slot_label}   {_m(value)}", sz=SZ)
        draw(c, 200, y, description, sz=SZ_SM)
        y -= LH_W2
    y -= LH_W2 * 0.5

    # Box 14 — informational only, not parsed (optional)
    if d.get('box14_entries'):
        for label, value in d['box14_entries']:
            draw(c, 36, y, f"14  Other   {label}  {_m(value)}", sz=SZ)
            y -= LH_W2
        y -= LH_W2 * 0.5

    hline(c, y)
    y -= LH_W2 * 1.5

    # State boxes 15/16/17 — each on a distinct y for the parser regex
    draw(c, 36,  y, "15  State  Employer's state ID number", sz=SZ)
    draw(c, 310, y, f"{d['state']}  {d['er_state_id']}", sz=SZ)
    y -= LH_W2
    draw(c, 36,  y, "16  State wages, tips, etc.", sz=SZ)
    y -= LH_W2
    draw(c, 36,  y, f"{d['state']}  {d['er_state_id']}  {_m(d['state_wages'])}", sz=SZ)
    y -= LH_W2
    draw(c, 36,  y, "17  State income tax", sz=SZ)
    y -= LH_W2
    draw(c, 36,  y, _m(d['state_tax']), FONT_MONO, SZ)
    y -= LH_W2 * 2
    hline(c, y)
    y -= LH_W2
    draw(c, 36, y, "Copy B — To Be Filed With Employee's FEDERAL Tax Return", sz=SZ_SM)
    y -= LH_W2
    draw(c, 36, y,
         "This information is being furnished to the Internal Revenue Service.",
         sz=SZ_SM)


# =============================================================================
# Microsoft  —  ADP-style paystub (2-page layout)
# =============================================================================
#
# x-coordinates are critical for position-aware extraction:
#   Left "This Period" values : drawRightString at CURR_X=240  → chars x < 250  ✓
#   Left "YTD" values         : drawRightString at YTD_X=325   → chars 250–340  ✓
#   Right column labels/values: x ≥ RLBL_X=348                → ignored

LBL_X   = 72    # left labels start (1 inch)
RATE_X  = 160   # hours column right edge
CURR_X  = 240   # left "This Period" right edge
YTD_X   = 325   # left "YTD" right edge
RLBL_X  = 348   # right column labels start
RCURR_X = 468   # right column "This Period" right edge
RYTD_X  = 570   # right column "YTD" right edge
LH_PS   = 11    # paystub line height

def _n(v): return f"{abs(v):,.2f}"         # positive money string
def _d(v): return f"{abs(v):,.2f}-"        # deduction string (trailing minus)

def num_l(c, x, y, text):
    c.setFont(FONT_MONO, SZ); c.drawRightString(x, y, text)

def num_r(c, x, y, text):
    c.setFont(FONT_MONO, SZ); c.drawRightString(x, y, text)


def _msft_header(c, emp, paystub, page_num, total_pages):
    y = H - 10
    # Disclaimer banner at the very top
    c.setFillColorRGB(0.95, 0.95, 0.95)
    c.rect(LBL_X, y - 10, 580 - LBL_X, 13, fill=1, stroke=0)
    c.setFillColorRGB(0, 0, 0)
    draw(c, LBL_X, y - 8, emp.get("disclaimer", ""), sz=SZ_SM)
    y -= 18
    draw(c, LBL_X, y,
         f"Page {page_num:03d} of {total_pages:03d}    "
         f"CO 000000-000000    Earnings Statement", sz=SZ_SM)
    y -= 18
    draw(c, RLBL_X, y, "Microsoft Corporation", font=FONT_BOLD)
    draw(c, LBL_X,  y, f"Employee ID  {emp['id']}")
    y -= LH_PS
    draw(c, RLBL_X, y, "One Microsoft Way")
    draw(c, LBL_X,  y, f"Period Beg/End: {paystub['period_beg']} - {paystub['period_end']}")
    y -= LH_PS
    draw(c, RLBL_X, y, "Redmond, WA  98052-6399")
    draw(c, LBL_X,  y, f"Advice Date: {paystub['advice_date']}")
    y -= LH_PS
    draw(c, LBL_X,  y, f"Advice Number: {paystub['advice_number']}")
    y -= LH_PS
    draw(c, LBL_X,  y, f"Batch Number: {paystub['batch']}")
    draw(c, RLBL_X, y, "For Payroll/Benefits inquiries call: 425-706-8853")
    y -= LH_PS
    draw(c, LBL_X, y, emp['name'], font=FONT_BOLD)
    y -= LH_PS
    draw(c, LBL_X, y, emp['addr1'])
    y -= LH_PS
    draw(c, LBL_X, y, emp['addr2'])
    y -= LH_PS
    draw(c, LBL_X, y, "Basis of Pay: Salary")
    y -= 4
    hline(c, y, x0=LBL_X, x1=580)
    return y - 8


def draw_msft_page1(c, emp, p):
    y = _msft_header(c, emp, p, 1, 2)

    c.setFont(FONT_BOLD, SZ_SM)
    c.drawString(LBL_X, y, "Earnings")
    c.drawRightString(RATE_X, y, "Hours")
    c.drawRightString(CURR_X, y, "This Period")
    c.drawRightString(YTD_X,  y, "Year-to-Date")
    c.drawRightString(RCURR_X, y, "This Period")
    c.drawRightString(RYTD_X,  y, "Year-to-Date")
    y -= 3
    hline(c, y, x0=LBL_X, x1=580)
    y -= LH_PS

    has_rsu = p.get('stock_award', 0) > 0

    # Row 0 — Base Salary | "Retirement" header (no numbers — must be separate y)
    draw(c, LBL_X, y, "Base Salary")
    num_l(c, RATE_X, y, f"{p['hours']:.2f}")
    num_l(c, CURR_X, y, _n(p['base']));   num_l(c, YTD_X, y, _n(p['ytd_base']))
    draw(c, RLBL_X, y, "Retirement", font=FONT_BOLD)
    y -= LH_PS

    # Row 1 — Stock Award or Perks+ | *401K Pre Tax
    if has_rsu:
        draw(c, LBL_X, y, "Stock Award Income")
        num_l(c, CURR_X, y, _n(p['stock_award'])); num_l(c, YTD_X, y, _n(p['ytd_stock_award']))
    else:
        draw(c, LBL_X, y, "Perks+ Taxable")
        num_l(c, CURR_X, y, _n(p['perks']));       num_l(c, YTD_X, y, _n(p['ytd_perks']))
    draw(c, RLBL_X, y, "*401K Pre Tax")
    num_r(c, RCURR_X, y, _d(p['pretax_401k']));    num_r(c, RYTD_X, y, _d(p['ytd_pretax_401k']))
    y -= LH_PS

    # Row 2 — Perks+ (RSU) or Total Earnings | 401K After Tax
    if has_rsu:
        draw(c, LBL_X, y, "Perks+ Taxable")
        num_l(c, CURR_X, y, _n(p['perks']));       num_l(c, YTD_X, y, _n(p['ytd_perks']))
    else:
        draw(c, LBL_X, y, "Total Earnings", font=FONT_BOLD)
        num_l(c, CURR_X, y, _n(p['gross']));       num_l(c, YTD_X, y, _n(p['ytd_gross']))
    draw(c, RLBL_X, y, "401K After Tax")
    num_r(c, RCURR_X, y, _d(p['aftertax_401k']));  num_r(c, RYTD_X, y, _d(p['ytd_aftertax_401k']))
    y -= LH_PS

    # Row 3 — Total Earnings (RSU) or blank | 401K Roth
    if has_rsu:
        draw(c, LBL_X, y, "Total Earnings", font=FONT_BOLD)
        num_l(c, CURR_X, y, _n(p['gross']));       num_l(c, YTD_X, y, _n(p['ytd_gross']))
    draw(c, RLBL_X, y, "401K Roth")
    num_r(c, RCURR_X, y, _d(p['roth_401k']));      num_r(c, RYTD_X, y, _d(p['ytd_roth_401k']))
    y -= LH_PS

    draw(c, RLBL_X, y, "Total Retirement", font=FONT_BOLD)
    num_r(c, RCURR_X, y, _d(p['total_retirement'])); num_r(c, RYTD_X, y, _d(p['ytd_total_retirement']))
    y -= LH_PS

    draw(c, RLBL_X, y, "Net Pay", font=FONT_BOLD)
    num_r(c, RCURR_X, y, _n(p['net_pay']));        num_r(c, RYTD_X, y, _n(p['ytd_net_pay']))
    y -= 4;  hline(c, y, x0=LBL_X, x1=580);  y -= LH_PS

    draw(c, LBL_X, y, "Taxes", font=FONT_BOLD)
    draw(c, RLBL_X, y, "Net Pay Distribution", font=FONT_BOLD)
    y -= LH_PS

    draw(c, LBL_X, y, "Federal Income Tax")
    num_l(c, CURR_X, y, _d(p['fed_tax']));         num_l(c, YTD_X, y, _d(p['ytd_fed_tax']))
    draw(c, RLBL_X, y, f"XXXXX{p['acct_last5']}  {_n(p['net_pay'])}  Savings")
    y -= LH_PS

    draw(c, LBL_X, y, "Social Security Tax")
    num_l(c, CURR_X, y, _d(p['ss_tax']));          num_l(c, YTD_X, y, _d(p['ytd_ss_tax']))
    draw(c, RLBL_X, y, "Other Benefits and Information", font=FONT_BOLD)
    y -= LH_PS

    draw(c, LBL_X, y, "Medicare Tax")
    num_l(c, CURR_X, y, _d(p['medicare_tax']));    num_l(c, YTD_X, y, _d(p['ytd_medicare_tax']))
    draw(c, RLBL_X, y, "Imputed Life Ins")
    num_r(c, RCURR_X, y, _n(p['ltd_imputed']));    num_r(c, RYTD_X, y, _n(p['ytd_ltd_imputed']))
    y -= LH_PS

    draw(c, LBL_X, y, "UT W/H Tax")
    num_l(c, CURR_X, y, _d(p['state_tax']));       num_l(c, YTD_X, y, _d(p['ytd_state_tax']))
    draw(c, RLBL_X, y, "401K Employer Match")
    num_r(c, RCURR_X, y, _n(p['employer_match'])); num_r(c, RYTD_X, y, _n(p['ytd_employer_match']))
    y -= LH_PS

    draw(c, LBL_X, y, "Total Taxes", font=FONT_BOLD)
    num_l(c, CURR_X, y, _d(p['total_taxes']));     num_l(c, YTD_X, y, _d(p['ytd_total_taxes']))
    y -= 4;  hline(c, y, x0=LBL_X, x1=580);  y -= LH_PS

    draw(c, LBL_X, y, "Benefits", font=FONT_BOLD)
    draw(c, RLBL_X, y, "Personal Time Balance", font=FONT_BOLD)
    y -= LH_PS

    draw(c, LBL_X, y, "*DCFSA Deduction")
    num_l(c, CURR_X, y, _d(p['dcfsa']));           num_l(c, YTD_X, y, _d(p['ytd_dcfsa']))
    draw(c, RLBL_X, y, "Description");  draw(c, RLBL_X + 80, y, "Balance")
    y -= LH_PS

    draw(c, LBL_X, y, "*LPFSA Deduction")
    num_l(c, CURR_X, y, _d(p['lpfsa']));           num_l(c, YTD_X, y, _d(p['ytd_lpfsa']))
    draw(c, RLBL_X, y, "HHTO");  draw(c, RLBL_X + 60, y, f"{p['hhto_balance']:.2f}")
    y -= LH_PS

    draw(c, LBL_X, y, "*HSA EE Contribution")
    num_l(c, CURR_X, y, _d(p['hsa_ee']));          num_l(c, YTD_X, y, _d(p['ytd_hsa_ee']))
    y -= LH_PS

    draw(c, LBL_X, y, "AD&D Family Ins")
    num_l(c, CURR_X, y, _d(p['add_ins']));         num_l(c, YTD_X, y, _d(p['ytd_add_ins']))
    y -= LH_PS

    draw(c, LBL_X, y, "Long Term Dis Imputed Inc")
    num_l(c, CURR_X, y, _n(p['ltd_imputed']));     num_l(c, YTD_X, y, _n(p['ytd_ltd_imputed']))
    y -= LH_PS

    # ESPP must start at line-left for pattern r"^\s*ESPP\b"
    draw(c, LBL_X, y, "ESPP")
    num_l(c, CURR_X, y, _d(p['espp']));            num_l(c, YTD_X, y, _d(p['ytd_espp']))
    y -= LH_PS

    draw(c, LBL_X, y, "Total Benefits", font=FONT_BOLD)
    num_l(c, CURR_X, y, _d(p['total_benefits']));  num_l(c, YTD_X, y, _d(p['ytd_total_benefits']))
    y -= 4;  hline(c, y, x0=LBL_X, x1=580);  y -= LH_PS

    draw(c, LBL_X, y, "* Excluded from Federal Taxable Wages", sz=SZ_SM);  y -= LH_PS
    draw(c, LBL_X, y, f"Federal taxable wages for the period:  {_n(p['fed_taxable_wages'])}", sz=SZ_SM);  y -= LH_PS
    draw(c, LBL_X, y, f"Federal taxable wages for the year:    {_n(p['ytd_fed_taxable_wages'])}", sz=SZ_SM);  y -= LH_PS
    draw(c, LBL_X, y, "Federal taxable wage calculator    aka.ms/fedtaxablewages", sz=SZ_SM)
    y -= LH_PS * 2;  hline(c, y, x0=LBL_X, x1=580);  y -= LH_PS
    draw(c, LBL_X, y, "2002 Automatic Data Processing (PCSUVO)", sz=SZ_SM)
    y -= LH_PS * 2;  hline(c, y, x0=LBL_X, x1=580);  y -= LH_PS

    draw(c, LBL_X, y, "Microsoft Corporation", font=FONT_BOLD)
    draw(c, 320,   y, f"Advice Number: {p['advice_number']}")
    y -= LH_PS
    draw(c, LBL_X, y, "One Microsoft Way   Redmond, WA  98052-6399")
    draw(c, 320,   y, f"Advice Date: {p['advice_date']}")
    y -= LH_PS
    draw(c, LBL_X, y,
         f"{emp['name']}   Savings   XXXXX{p['acct_last5']}   "
         f"{p['routing']}   {_n(p['net_pay'])}")


def draw_msft_page2(c, emp, p):
    y = _msft_header(c, emp, p, 2, 2)

    c.setFont(FONT_BOLD, SZ_SM)
    c.drawString(LBL_X, y, "Earnings")
    c.drawRightString(CURR_X, y, "This Period")
    c.drawRightString(YTD_X,  y, "Year-to-Date")
    y -= 3;  hline(c, y, x0=LBL_X, x1=580);  y -= LH_PS

    if p.get('stock_award', 0) > 0:
        draw(c, LBL_X, y, "Other", font=FONT_BOLD);  y -= LH_PS

        draw(c, LBL_X, y, "Stock Award Taxes Offset")
        num_l(c, CURR_X, y, _n(p['stock_taxes_offset']))
        num_l(c, YTD_X,  y, _n(p['ytd_stock_taxes_offset']))
        y -= LH_PS

        draw(c, LBL_X, y, "Long Term Dis Offset")
        num_l(c, CURR_X, y, _d(p['ltd_imputed']));   num_l(c, YTD_X, y, _d(p['ytd_ltd_imputed']))
        y -= LH_PS

        draw(c, LBL_X, y, "Stock Award Income Offset")
        num_l(c, CURR_X, y, _d(p['stock_award']));   num_l(c, YTD_X, y, _d(p['ytd_stock_award']))
        y -= LH_PS

        total_other     = p['stock_taxes_offset'] - p['ltd_imputed'] - p['stock_award']
        ytd_total_other = p['ytd_stock_taxes_offset'] - p['ytd_ltd_imputed'] - p['ytd_stock_award']
        draw(c, LBL_X, y, "Total Other", font=FONT_BOLD)
        num_l(c, CURR_X, y, _d(abs(total_other)));   num_l(c, YTD_X, y, _d(abs(ytd_total_other)))
        y -= LH_PS * 2;  hline(c, y, x0=LBL_X, x1=580);  y -= LH_PS

        draw(c, LBL_X, y, "The following earnings from prior pay periods are being", sz=SZ_SM);  y -= LH_PS
        draw(c, LBL_X, y, "paid in this period and included in the Earnings on page 1", sz=SZ_SM);  y -= LH_PS
        draw(c, LBL_X, y, "Earning Period", font=FONT_BOLD)
        draw(c, 160,   y, "Hours",  font=FONT_BOLD)
        draw(c, 200,   y, "Rate",   font=FONT_BOLD)
        draw(c, 240,   y, "Amount", font=FONT_BOLD)
        y -= LH_PS
        vest = p['advice_date'][:5]
        draw(c, LBL_X, y, "Stock Award Incom")
        draw(c, 160,   y, f"{vest}-{vest}")
        num_l(c, CURR_X, y, _n(p['stock_award']))
    else:
        draw(c, LBL_X, y, "The following earnings from prior pay periods are being", sz=SZ_SM);  y -= LH_PS
        draw(c, LBL_X, y, "paid in this period and included in the Earnings on page 1", sz=SZ_SM);  y -= LH_PS
        draw(c, LBL_X, y, "(none)", sz=SZ_SM)

    y -= LH_PS * 2;  hline(c, y, x0=LBL_X, x1=580);  y -= LH_PS
    draw(c, LBL_X, y, "2002 Automatic Data Processing (PCSUVO)", sz=SZ_SM)


def generate_msft_paystub_pdf(out_path: Path, emp: dict, paystub: dict):
    c = canvas.Canvas(str(out_path), pagesize=letter)
    draw_msft_page1(c, emp, paystub)
    c.showPage()
    draw_msft_page2(c, emp, paystub)
    c.showPage()
    c.save()
    print(f"  PDF  → {out_path.name}")


# ── Microsoft data ─────────────────────────────────────────────────────────────

MSFT_DISCLAIMER = (
    "SYNTHETIC DEMO DATA — All names, wages, and financial figures are "
    "entirely fictitious and generated for testing purposes only."
)

MSFT_EMP = {
    "id":        "00000000",
    "name":      "Test MS Name",
    "addr1":     "8523 Oakwood Drive",
    "addr2":     "Seattle, WA  98112",
    "disclaimer": MSFT_DISCLAIMER,
}

# Paystub 1: 2018-04-15  (period 7, regular salary – no RSU)
# gross = base($4,950) + perks($50) = $5,000
# SS not yet capped at period 7: ytd wages $35,000 < $128,400 cap
# Invariant: gross − pretax($385) − taxes($1,531) − aftertax($339.50) = net_pay($2,744.50) ✓
MSFT_P1 = dict(
    advice_date="04/15/2018", advice_number="024875310070",
    period_beg="04/01/2018",  period_end="04/15/2018",
    batch="000000000007",     acct_last5="3842",  routing="111111111",
    hours=86.67,

    base=4950.00,   ytd_base=34650.00,    # $4,950 × 7 periods
    stock_award=0.0, ytd_stock_award=0.0,
    perks=50.00,    ytd_perks=350.00,
    gross=5000.00,  ytd_gross=35000.00,

    # Pretax deductions (right-column Retirement section)
    pretax_401k=192.00,  ytd_pretax_401k=1344.00,   # toward annual $5,000 target
    hsa_ee=77.00,        ytd_hsa_ee=539.00,           # toward annual $2,002
    # Pretax deductions (left-column Benefits section)
    dcfsa=96.00,         ytd_dcfsa=672.00,
    lpfsa=20.00,         ytd_lpfsa=140.00,

    # After-tax deductions
    aftertax_401k=50.00, ytd_aftertax_401k=350.00,
    roth_401k=38.00,     ytd_roth_401k=266.00,        # toward annual $988
    espp=250.00,         ytd_espp=1750.00,
    add_ins=1.50,        ytd_add_ins=10.50,

    total_retirement=280.00,   ytd_total_retirement=1960.00,
    total_benefits=429.50,     ytd_total_benefits=3006.50,
    # total_benefits = hsa_ee+dcfsa+lpfsa+add_ins+espp − ltd_imputed
    # = 77+96+20+1.50+250 − 15 = 429.50 ✓

    fed_tax=920.00,      ytd_fed_tax=6440.00,
    ss_tax=310.00,       ytd_ss_tax=2170.00,    # 6.2% × $5,000; cap not yet hit
    medicare_tax=73.00,  ytd_medicare_tax=511.00,
    state_tax=228.00,    ytd_state_tax=1596.00,  # ~4.95% UT on taxable wages
    total_taxes=1531.00, ytd_total_taxes=10717.00,

    net_pay=2744.50, ytd_net_pay=19211.50,
    # Check: 5000 − 385(pretax) − 1531(taxes) − 339.50(aftertax) = 2744.50 ✓

    ltd_imputed=15.00,        ytd_ltd_imputed=105.00,
    employer_match=200.00,    ytd_employer_match=1400.00,
    fed_taxable_wages=4615.00, ytd_fed_taxable_wages=32305.00,  # gross − pretax
    hhto_balance=75.00,
    stock_taxes_offset=0.0,   ytd_stock_taxes_offset=0.0,
)

# Paystub 2: 2018-09-13  (period 17, salary raise – no RSU)
# gross = base($5,950) + perks($50) = $6,000  (raise effective period 8)
# SS not yet capped at period 17: ytd wages $95,000 < $128,400 cap
# Invariant: gross − pretax($385) − taxes($2,027) − aftertax($389.50) = net_pay($3,198.50) ✓
MSFT_P2 = dict(
    advice_date="09/13/2018", advice_number="024875310170",
    period_beg="08/30/2018",  period_end="09/13/2018",
    batch="000000000017",     acct_last5="3842",  routing="111111111",
    hours=86.67,

    # YTD: periods 1–7 at $5,000 + periods 8–17 at $6,000 = $35,000 + $60,000
    base=5950.00,   ytd_base=94150.00,    # $4,950×7 + $5,950×10
    stock_award=0.0, ytd_stock_award=0.0,
    perks=50.00,    ytd_perks=850.00,
    gross=6000.00,  ytd_gross=95000.00,

    pretax_401k=192.00,  ytd_pretax_401k=3264.00,   # $192 × 17
    hsa_ee=77.00,        ytd_hsa_ee=1309.00,
    dcfsa=96.00,         ytd_dcfsa=1632.00,
    lpfsa=20.00,         ytd_lpfsa=340.00,

    aftertax_401k=50.00, ytd_aftertax_401k=850.00,
    roth_401k=38.00,     ytd_roth_401k=646.00,
    espp=300.00,         ytd_espp=4750.00,   # $250×7 + $300×10
    add_ins=1.50,        ytd_add_ins=25.50,

    total_retirement=280.00,   ytd_total_retirement=4760.00,
    total_benefits=479.50,     ytd_total_benefits=7801.50,
    # total_benefits = 77+96+20+1.50+300 − 15 = 479.50 ✓
    # ytd_total_benefits = 429.50×7 + 479.50×10 = 3006.50 + 4795 = 7801.50 ✓

    fed_tax=1290.00,     ytd_fed_tax=19340.00,   # $920×7 + $1,290×10
    ss_tax=372.00,       ytd_ss_tax=5890.00,     # 6.2% × $6,000; $310×7 + $372×10
    medicare_tax=87.00,  ytd_medicare_tax=1381.00,
    state_tax=278.00,    ytd_state_tax=4376.00,
    total_taxes=2027.00, ytd_total_taxes=30987.00,

    net_pay=3198.50, ytd_net_pay=51196.50,
    # Check: 6000 − 385(pretax) − 2027(taxes) − 389.50(aftertax) = 3198.50 ✓

    ltd_imputed=15.00,        ytd_ltd_imputed=255.00,
    employer_match=200.00,    ytd_employer_match=3400.00,
    fed_taxable_wages=5615.00, ytd_fed_taxable_wages=88455.00,  # $4,615×7 + $5,615×10
    hhto_balance=62.50,
    stock_taxes_offset=0.0,   ytd_stock_taxes_offset=0.0,
)

MSFT_W2 = dict(
    year=2018, ssn="XXX-XX-1234", ein="91-1144442",
    emp_name="Test MS Name",
    emp_addr1="8523 Oakwood Drive", emp_addr2="Seattle, WA  98112",
    er_name="Microsoft Corporation",
    er_addr1="One Microsoft Way",   er_addr2="Redmond, WA  98052-6399",
    er_state_id="91-1144442",

    # Box 1 wages = $150,000 gross − $5,000 401k − $2,000 HSA = $143,000
    wages=143000.00,      federal_tax=28000.00,
    ss_wages=128400.00,   ss_tax=7960.80,          # 2018 SS cap = $128,400
    medicare_wages=143000.00, medicare_tax=2073.50,  # 1.45% × $143,000
    state="UT", state_wages=143000.00, state_tax=7150.00,  # ~5% UT

    box12_entries=[
        ("12a  C",  300.00,  "Taxable group-term life ins."),
        ("12b  D",  5000.00, "401(k) elective deferrals (pre-tax)"),
        ("12c  W",  2000.00, "HSA contributions"),
        ("12d  AA", 1000.00, "Roth 401(k) contributions"),
    ],
    box14_entries=[("ESPP", 8000.00)],   # ESPP gains for the year
    disclaimer=MSFT_DISCLAIMER,
)


# =============================================================================
# UofU  —  single-page paystub
# =============================================================================
#
# Critical lines for the parser (each at a distinct y):
#   "Advice Date: 04/30/2024"                                      → pay date
#   "Current 3,000.00 2,414.35 567.51 598.30 1,834.19"            → summary
#   "Fed Withhold  241.44  1,690.08"  … "UT Withhold  96.57 …"    → taxes
#   "BlueCross …  189.50 …"  "403(b) TDA  300.00 …"  "FSA …"      → pretax ded.
#   "Basic Life …  10.50 …"  "Life Plan 2 Child  2.15 …"          → aftertax ded.
#   "TOTAL: 585.65 … TOTAL: 12.65 … *TAXABLE"                     → ded. totals

SZ_LG_UOFU = 11
LH_UOFU    = 13

UOFU_DISCLAIMER = (
    "SYNTHETIC DEMO DATA — Name changed for privacy. Wages based on public "
    "UofU salary data for IT Analyst II (~$78k/yr, 2024). Not a real document."
)

UOFU_PERIODS = 7  # pay periods elapsed YTD including this one

def _ytd(v: float) -> float:
    return round(v * UOFU_PERIODS, 2)


def draw_uofu_paystub(c, d):
    y = H - 36

    draw(c, 36,  y, "UNIVERSITY OF UTAH",          FONT_BOLD, SZ_LG_UOFU)
    draw(c, 360, y, "EMPLOYEE EARNINGS STATEMENT",  FONT_BOLD, SZ)
    y -= LH_UOFU
    draw(c, 36,  y, "Human Resources & Payroll",    sz=SZ_SM)
    draw(c, 360, y, d['disclaimer'],                sz=6)
    y -= LH_UOFU * 1.5
    hline(c, y);  y -= LH_UOFU * 1.5

    draw(c, 36,  y, f"Employee:    {d['emp_name']}",  sz=SZ)
    draw(c, 300, y, f"Advice Date: {d['advice_date']}", FONT_BOLD, SZ)
    y -= LH_UOFU
    draw(c, 36,  y, f"Employee ID: {d['emp_id']}",    sz=SZ)
    draw(c, 300, y, "Pay Frequency: Bi-Weekly",        sz=SZ)
    y -= LH_UOFU
    draw(c, 36,  y, f"Department:  {d['department']}", sz=SZ)
    draw(c, 300, y, f"Period: {d['period_start']} - {d['period_end']}", sz=SZ)
    y -= LH_UOFU
    draw(c, 36,  y, f"Title:       {d['title']}",     sz=SZ)
    y -= LH_UOFU * 1.5
    hline(c, y);  y -= LH_UOFU

    draw(c, 36,  y, "DESCRIPTION",   FONT_BOLD, SZ_SM)
    draw(c, 340, y, "CURRENT",       FONT_BOLD, SZ_SM)
    draw(c, 450, y, "YEAR TO DATE",  FONT_BOLD, SZ_SM)
    y -= LH_UOFU * 0.5
    hline(c, y);  y -= LH_UOFU

    draw(c, 36, y, "EARNINGS", FONT_BOLD, SZ);  y -= LH_UOFU
    draw(c, 50,  y, "Base Salary",            sz=SZ)
    draw(c, 340, y, _m(d['gross']),           FONT_MONO, SZ)
    draw(c, 450, y, _m(_ytd(d['gross'])),     FONT_MONO, SZ)
    y -= LH_UOFU * 1.5

    # Summary line — all 5 numbers on ONE extracted line (same y)
    draw(c, 36, y,
         f"Current  {_m(d['gross'])}  {_m(d['fed_taxable'])}  "
         f"{_m(d['taxes_total'])}  {_m(d['total_deductions'])}  {_m(d['net_pay'])}",
         FONT_BOLD, SZ_SM)
    y -= LH_UOFU
    draw(c, 36, y,
         f"YTD      {_m(_ytd(d['gross']))}  {_m(_ytd(d['fed_taxable']))}  "
         f"{_m(_ytd(d['taxes_total']))}  {_m(_ytd(d['total_deductions']))}  {_m(_ytd(d['net_pay']))}",
         sz=SZ_SM)
    y -= LH_UOFU * 1.5
    hline(c, y);  y -= LH_UOFU

    draw(c, 36, y, "TAXES", FONT_BOLD, SZ);  y -= LH_UOFU
    for label, curr in [
        ("Fed Withhold", d['fed_wh']),
        ("Fed OASDI/EE", d['ss']),
        ("Fed MED/EE",   d['medicare']),
        ("UT Withhold",  d['state_wh']),
    ]:
        draw(c, 50, y, f"{label}  {_m(curr)}  {_m(_ytd(curr))}", sz=SZ);  y -= LH_UOFU
    y -= LH_UOFU * 0.5
    hline(c, y);  y -= LH_UOFU

    draw(c, 36, y, "BEFORE-TAX DEDUCTIONS", FONT_BOLD, SZ);  y -= LH_UOFU
    for label, curr in [
        ("BlueCross BlueShield Med/Den", d['bb_insurance']),
        ("403(b) TDA",                  d['tda_403b']),
        ("FSA Health",                  d['fsa_health']),
    ]:
        draw(c, 50, y, f"{label}  {_m(curr)}  {_m(_ytd(curr))}", sz=SZ);  y -= LH_UOFU
    y -= LH_UOFU * 0.5

    draw(c, 36, y, "AFTER-TAX DEDUCTIONS", FONT_BOLD, SZ);  y -= LH_UOFU
    for label, curr in [
        ("Basic Life Employee", d['life_emp']),
        ("Life Plan 2 Child",   d['life_child']),
    ]:
        draw(c, 50, y, f"{label}  {_m(curr)}  {_m(_ytd(curr))}", sz=SZ);  y -= LH_UOFU
    y -= LH_UOFU * 0.5

    # Totals line — parser needs: TOTAL: <pretax> ... TOTAL: <aftertax> ... *TAXABLE
    draw(c, 36, y,
         f"TOTAL: {_m(d['pretax_total'])}  {_m(_ytd(d['pretax_total']))}  "
         f"TOTAL: {_m(d['aftertax_total'])}  {_m(_ytd(d['aftertax_total']))}  *TAXABLE",
         FONT_BOLD, SZ_SM)
    y -= LH_UOFU * 1.5
    hline(c, y);  y -= LH_UOFU

    draw(c, 36, y, "NET PAY DISTRIBUTION", FONT_BOLD, SZ);  y -= LH_UOFU
    draw(c, 50,  y, "Direct Deposit  ****5678", sz=SZ)
    draw(c, 340, y, _m(d['net_pay']),             FONT_BOLD, SZ)
    y -= LH_UOFU * 2;  hline(c, y);  y -= LH_UOFU
    draw(c, 36, y,
         "University of Utah  •  201 Presidents' Circle, Salt Lake City, UT 84112",
         sz=SZ_SM)


# ── UofU data ─────────────────────────────────────────────────────────────────

_UOFU_PS_RAW = dict(
    emp_name="Test U Name", emp_id="U0000001",
    department="Information Technology", title="IT Analyst II",
    advice_date="04/30/2024", period_start="04/16/2024", period_end="04/30/2024",
    gross=3_000.00,
    bb_insurance=189.50,  # BlueCross BlueShield Med/Den
    tda_403b=300.00,      # 403(b) TDA
    fsa_health=96.15,     # FSA Health
    fed_wh=241.44,        # Federal income tax withholding
    ss=186.00,            # Fed OASDI/EE  (6.2% × $3,000)
    medicare=43.50,       # Fed MED/EE    (1.45% × $3,000)
    state_wh=96.57,       # UT Withhold
    life_emp=10.50,       # Basic Life Employee
    life_child=2.15,      # Life Plan 2 Child
    disclaimer=UOFU_DISCLAIMER,
)
_UOFU_PS_RAW["pretax_total"]     = round(_UOFU_PS_RAW["bb_insurance"] + _UOFU_PS_RAW["tda_403b"] + _UOFU_PS_RAW["fsa_health"], 2)
_UOFU_PS_RAW["aftertax_total"]   = round(_UOFU_PS_RAW["life_emp"] + _UOFU_PS_RAW["life_child"], 2)
_UOFU_PS_RAW["taxes_total"]      = round(_UOFU_PS_RAW["fed_wh"] + _UOFU_PS_RAW["ss"] + _UOFU_PS_RAW["medicare"] + _UOFU_PS_RAW["state_wh"], 2)
_UOFU_PS_RAW["fed_taxable"]      = round(_UOFU_PS_RAW["gross"] - _UOFU_PS_RAW["pretax_total"], 2)
_UOFU_PS_RAW["total_deductions"] = round(_UOFU_PS_RAW["pretax_total"] + _UOFU_PS_RAW["aftertax_total"], 2)
_UOFU_PS_RAW["net_pay"]          = round(
    _UOFU_PS_RAW["gross"] - _UOFU_PS_RAW["pretax_total"]
    - _UOFU_PS_RAW["taxes_total"] - _UOFU_PS_RAW["aftertax_total"], 2
)
assert abs(_UOFU_PS_RAW["gross"] - _UOFU_PS_RAW["net_pay"]
           - _UOFU_PS_RAW["taxes_total"] - _UOFU_PS_RAW["total_deductions"]) < 0.02, \
    "UofU paystub equation does not balance!"

UOFU_PS = _UOFU_PS_RAW

_pt = UOFU_PS["pretax_total"]
UOFU_W2 = dict(
    year=2024, ssn="XXX-XX-5678", ein="87-6000512",
    emp_name="Test U Name",
    emp_addr1="4521 Campus Drive", emp_addr2="Salt Lake City, UT  84112",
    er_name="University of Utah",
    er_addr1="201 Presidents' Circle", er_addr2="Salt Lake City, UT  84112",
    er_state_id="87-6000512",

    # Box 1: wages = gross×26 − pretax deductions×26
    wages=round(78_000.00 - _pt * 26, 2),           # 62,773.10
    federal_tax=round(UOFU_PS["fed_wh"] * 26, 2),   # 6,277.44

    # Box 3/4: SS wages (no cap hit — $78k < $168,600 for 2024)
    ss_wages=78_000.00,
    ss_tax=round(78_000.00 * 0.062, 2),              # 4,836.00

    # Box 5/6: Medicare (no cap)
    medicare_wages=78_000.00,
    medicare_tax=round(78_000.00 * 0.0145, 2),       # 1,131.00

    state="UT",
    state_wages=round(78_000.00 - _pt * 26, 2),
    state_tax=round(UOFU_PS["state_wh"] * 26, 2),   # 2,510.82

    # Box 12 — UofU: 403(b) only; no HSA match, no Roth, no GTL
    box12_entries=[
        ("12a  D", round(UOFU_PS["tda_403b"] * 26, 2), "403(b) elective deferrals (pre-tax)"),
    ],
    disclaimer=UOFU_DISCLAIMER,
)


# =============================================================================
# Main
# =============================================================================

def _dirs(person: str, *subs: str):
    base = PROJECT_ROOT / "data" / "raw" / person
    for sub in subs:
        (base / sub).mkdir(parents=True, exist_ok=True)
    return base


if __name__ == "__main__":
    from backend.app.constants import EMPLOYER_MICROSOFT, EMPLOYER_U_OF_UTAH

    # ── DemoMicrosoftEmployee ──────────────────────────────────────────────────
    print("Generating DemoMicrosoftEmployee…")
    msft = _dirs("DemoMicrosoftEmployee", "paystub", "paystub_groundtruth", "w2", "w2_groundtruth")

    for stem, paystub in [
        ("Microsoft-Paystub-2018-04-15", MSFT_P1),
        ("Microsoft-Paystub-2018-09-13", MSFT_P2),
    ]:
        pdf   = msft / "paystub"             / f"{stem}.pdf"
        truth = msft / "paystub_groundtruth" / f"{stem}.json"
        generate_msft_paystub_pdf(pdf, MSFT_EMP, paystub)
        generate_paystub_groundtruth(pdf, truth, MSFT_DISCLAIMER)

    w2_pdf   = msft / "w2"             / f"Microsoft-W2-{MSFT_W2['year']}.pdf"
    w2_truth = msft / "w2_groundtruth" / f"Microsoft-W2-{MSFT_W2['year']}.json"
    generate_single_page_pdf(w2_pdf, draw_w2, MSFT_W2)
    generate_w2_groundtruth(w2_pdf, w2_truth, EMPLOYER_MICROSOFT,
                             "DemoMicrosoftEmployee", "demo0000", MSFT_DISCLAIMER)

    # ── DemoUofUEmployee ───────────────────────────────────────────────────────
    print("\nGenerating DemoUofUEmployee…")
    uofu = _dirs("DemoUofUEmployee", "paystub", "paystub_groundtruth", "w2", "w2_groundtruth")

    ps_stem  = f"UofU-Paystub-{UOFU_PS['advice_date'].replace('/', '-')}"
    ps_pdf   = uofu / "paystub"             / f"{ps_stem}.pdf"
    ps_truth = uofu / "paystub_groundtruth" / f"{ps_stem}.json"
    generate_single_page_pdf(ps_pdf, draw_uofu_paystub, UOFU_PS)
    generate_paystub_groundtruth(ps_pdf, ps_truth, UOFU_DISCLAIMER)

    w2_pdf   = uofu / "w2"             / f"UofU-W2-{UOFU_W2['year']}.pdf"
    w2_truth = uofu / "w2_groundtruth" / f"UofU-W2-{UOFU_W2['year']}.json"
    generate_single_page_pdf(w2_pdf, draw_w2, UOFU_W2)
    generate_w2_groundtruth(w2_pdf, w2_truth, EMPLOYER_U_OF_UTAH,
                             "DemoUofUEmployee", "uofu0001", UOFU_DISCLAIMER)

    print("\nDone. Run tests with:")
    print('  python -m pytest "tests/test_paystub_ingest_&_parse.py" "tests/test_w2_ingest_&_parse.py" -v')
