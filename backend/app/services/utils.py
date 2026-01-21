import pdfplumber
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List
from backend.app.constants import EMPLOYER_MICROSOFT, EMPLOYER_U_OF_UTAH, EMPLOYER_UNKNOWN

def detect_employer(filename_or_hint: str) -> str:
    f = filename_or_hint.lower()
    if "microsoft" in f or "msft" in f:
        return EMPLOYER_MICROSOFT
    if "utah" in f or "university" in f or "uou" in f or "UoU" in f:
        return EMPLOYER_U_OF_UTAH
    return EMPLOYER_UNKNOWN

# -----------------------------
# Extract PDF text (pdfplumber)
# -----------------------------

def extract_pdf_text(pdf_path: Path, max_pages: int = 2) -> str:
    """
    Keep it simple: payroll summaries are typically on page 1.
    Some MSFT have 2 pages; we take first 2.
    """
    chunks: List[str] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for i, page in enumerate(pdf.pages[:max_pages]):
            txt = page.extract_text() or ""
            if txt:
                chunks.append(txt)
    return "\n".join(chunks)
