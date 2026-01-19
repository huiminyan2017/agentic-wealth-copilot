from __future__ import annotations

import os
import json
import re
from typing import Optional
import pdfplumber
from pathlib import Path
from datetime import date, datetime
from backend.app.schemas import W2Record, PaystubRecord
from backend.app.services.storage import parsed_dir, repo_root
from backend.app.services.azure_docint import is_configured as azure_is_configured
from backend.app.services.paystub_azure_parser import parse_paystub_azure

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

def _infer_date(name: str) -> str:
    import re
    m = re.search(r"(20\d{2})[-_](\d{2})[-_](\d{2})", name)
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else "unknown"

def _sha256(p: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

# --- preview-time detection (fast) ---
def detect_doc_kind(filename: str) -> str:
    f = filename.lower()
    if "w2" in f or "w-2" in f:
        return "w2"
    if "pay" in f or "stub" in f or "adp" in f:
        return "paystub"
    return "unknown"

def detect_employer(filename_or_hint: str) -> str:
    f = filename_or_hint.lower()
    if "microsoft" in f or "msft" in f:
        return "microsoft"
    if "utah" in f or "university" in f:
        return "u_of_utah"
    return "unknown"

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

def _infer_date_from_filename(name: str) -> Optional[date]:
    m = re.search(r"(20\d{2})[-_](\d{2})[-_](\d{2})", name)
    if not m:
        return None
    return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))

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

def extract_pdf_text_local(pdf_path: Path) -> str:
    parts = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            if t.strip():
                parts.append(t)
    return "\n\n".join(parts).strip()


def parse_w2_local(pdf_path: Path, employer: str, person: str, sha8: str) -> W2Record:
    """
    Parse a Microsoft W-2 locally (text-based PDF).
    Flexible parse: fill what we can + warnings for missing fields.
    """
    extracted_text = extract_pdf_text_local(pdf_path)
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

# -----------------------------
# Microsoft ADP Paystub parser
# -----------------------------
def parse_paystub_local(pdf_path: Path, employer: str, person: str, sha8: str) -> PaystubRecord:
    extracted_text = extract_pdf_text_local(pdf_path)
    extracted_text_rel = _write_extracted_text(person, sha8, extracted_text)

    # ---- Pay date ----
    pay_date = None
    try:
        pay_date = _infer_date_from_filename(pdf_path.name)
    except Exception:
        pay_date = None

    if pay_date is None:
        m = re.search(r"Advice\s*Date:\s*(\d{2})/(\d{2})/(\d{4})", extracted_text)
        if m:
            mm, dd, yyyy = m.groups()
            try:
                pay_date = date(int(yyyy), int(mm), int(dd))
            except Exception:
                pay_date = None

    # ---- Earnings ----
    gross_pay, ytd_gross = find_two_money(
        r"\bTotal\s+Earnings\b.*?([0-9,]+\.\d{2}).*?([0-9,]+\.\d{2})",
        extracted_text
    )

    # ---- Federal taxable wages ----
    taxable_wages = find_money(
        r"Federal\s+taxable\s+wages\s+for\s+the\s+period[:\s]*\n?\s*([0-9,]+\.\d{2})",
        extracted_text
    )

    ytd_taxable_wages = find_money(
        r"Federal\s+taxable\s+wages[\s\S]{0,80}?year[\s\S]{0,40}?([0-9,]+\.\d{2})",
        extracted_text
    )

    # ---- Taxes ----
    federal_tax, ytd_federal_tax = find_two_money(
        r"\bFederal\s+Income\s+Tax\b.*?([0-9,]+\.\d{2})-.*?([0-9,]+\.\d{2})-",
        extracted_text
    )

    ss_tax, ytd_ss_tax = find_two_money(
        r"\bSocial\s+Security\s+Tax\b.*?([0-9,]+\.\d{2})-.*?([0-9,]+\.\d{2})-",
        extracted_text
    )

    medicare_tax, ytd_medicare_tax = find_two_money(
        r"\bMedicare\s+Tax\b.*?([0-9,]+\.\d{2})-.*?([0-9,]+\.\d{2})-",
        extracted_text
    )

    # Microsoft: "UT W/H Tax"
    state_tax, ytd_state_tax = find_two_money(
        r"\bUT\s+W/H\s+Tax\b.*?([0-9,]+\.\d{2})-.*?([0-9,]+\.\d{2})-",
        extracted_text
    )

    # ---- Net Pay ----
    net_pay, _ = find_two_money(
        r"\bNet\s+Pay\b.*?([0-9,]+\.\d{2}).*?([0-9,]+\.\d{2})",
        extracted_text
    )

    # ---- Deductions ----
    pre_tax = []
    post_tax = []

    def _maybe_add(pattern, bucket):
        v = find_money(pattern, extracted_text)
        if v is not None:
            bucket.append(v)

    # Pre-tax
    _maybe_add(r"\*401K\s+Pre\s+Tax\b.*?([0-9,]+\.\d{2})-", pre_tax)
    _maybe_add(r"\*HSA\s+EE\s+Contribution\b.*?([0-9,]+\.\d{2})-", pre_tax)
    _maybe_add(r"\*DCFSA\s+Deduction\b.*?([0-9,]+\.\d{2})-", pre_tax)
    _maybe_add(r"\*LPFSA\s+Deduction\b.*?([0-9,]+\.\d{2})-", pre_tax)

    # Post-tax
    _maybe_add(r"401K\s+After\s+Tax\b.*?([0-9,]+\.\d{2})-", post_tax)
    _maybe_add(r"401K\s+Roth\b.*?([0-9,]+\.\d{2})-", post_tax)
    _maybe_add(r"\bESPP\b.*?([0-9,]+\.\d{2})-", post_tax)

    pre_tax_deductions = sum(pre_tax) if pre_tax else None
    post_tax_deductions = sum(post_tax) if post_tax else None

    rec = PaystubRecord(
        pay_date=pay_date or date.today(),
        employer_name=employer,
        gross_pay=gross_pay,
        pre_tax_deductions=pre_tax_deductions,
        post_tax_deductions=post_tax_deductions,
        taxable_wages=taxable_wages,
        federal_tax=federal_tax,
        ss_tax=ss_tax,
        medicare_tax=medicare_tax,
        state_tax=state_tax,
        other_taxes=0.0,
        net_pay=net_pay,
        ytd_gross=ytd_gross,
        ytd_taxable_wages=ytd_taxable_wages,
        ytd_federal_tax=ytd_federal_tax,
        ytd_state_tax=ytd_state_tax,
        ytd_ss_tax=ytd_ss_tax,
        ytd_medicare_tax=ytd_medicare_tax,
        extracted_text_path=extracted_text_rel,
        source_pdf_relpath=_safe_relpath(pdf_path),
        notes=f"local parse: Microsoft ADP layout",
    )

    # ---- Missing-field warnings ----
    core_fields = [
        "gross_pay",
        "state_tax",
        "ytd_gross",
        "taxable_wages",
        "ytd_taxable_wages",
    ]

    missing = [f for f in core_fields if getattr(rec, f, None) is None]
    rec.missing_fields = missing

    if missing:
        rec.warnings.append(
            f"Missing {len(missing)} core fields: {', '.join(missing)}"
        )

    if pay_date is None:
        rec.warnings.append("Pay date not reliably detected")

    return rec



def _paystub_parser_mode() -> str:
    # azure | auto | local
    return (os.getenv("PAYSTUB_PARSER_MODE") or "azure").strip().lower()


def ingest_documents(person: str, paths: list[Path]):
    print(f"[INGEST] person={person}, num_files={len(paths)}")
    pdir = parsed_dir(person)
    index_path = pdir / "index.json"
    index = {"files": {}}  # sha256 -> record meta
    if index_path.exists():
        index = json.loads(index_path.read_text("utf-8"))

    ingested = 0
    skipped = 0
    errors: list[str] = []
    skipped_files = []
    skip_reasons = {}

    for pdf in paths:
        try:
            sha = _sha256(pdf)
            sha8 = sha[:8]

            if sha in index["files"]:
                skipped += 1
                skipped_files.append({
                    "path": str(pdf),
                    "reason": "already_ingested"
                })
                skip_reasons["already_ingested"] = skip_reasons.get("already_ingested", 0) + 1
                continue

            kind = detect_doc_kind(pdf.name)
            employer = detect_employer(pdf.name)

            if kind == "w2":
                rec = parse_w2_local(pdf, employer, person=person, sha8=sha8)
                out = pdir / "w2" / f"{rec.year}_{sha8}.json"
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(rec.model_dump_json(indent=2), "utf-8")

            elif kind == "paystub":
                mode = _paystub_parser_mode()

                if mode == "local":
                    rec = parse_paystub_local(pdf, employer, person=person, sha8=sha8)
                else:
                    if not azure_is_configured():
                        rec = parse_paystub_local(pdf, employer, person=person, sha8=sha8)
                        rec.warnings.append("Azure not configured; used deprecated local parser.")
                    else:
                        try:
                            print(f"[INGEST] Parsing paystub via Azure: {pdf}")
                            rec = parse_paystub_azure(pdf, employer, person=person, sha8=sha8)
                        except Exception as e:
                            # Fallback to local
                            rec = parse_paystub_local(pdf, employer, person=person, sha8=sha8)
                            rec.warnings.append(f"Azure parse failed; used deprecated local parser. Error: {type(e).__name__}: {e}")
                out = pdir / "paystub" / f"{rec.pay_date}_{sha8}.json"
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(rec.model_dump_json(indent=2), "utf-8")

            else:
                skipped += 1
                skipped_files.append({
                    "path": str(pdf),
                    "reason": "unknown_doc_type"
                })
                skip_reasons["unknown_doc_type"] = skip_reasons.get("unknown_doc_type", 0) + 1
                continue

            index["files"][sha] = {"rel": str(pdf), "kind": kind, "employer": employer}
            ingested += 1

        except Exception as e:
            skipped += 1
            reason = "parse_error"
            skipped_files.append({
                "path": str(pdf),
                "reason": reason,
                "error": str(e)
            })
            skip_reasons[reason] = skip_reasons.get(reason, 0) + 1

    index_path.write_text(json.dumps(index, indent=2), "utf-8")

    return {
        "ingested": ingested,
        "skipped": skipped,
        "skip_reasons": skip_reasons,
        "skipped_files": skipped_files,
        "errors": errors,
    }
