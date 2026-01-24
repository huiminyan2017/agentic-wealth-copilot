import pdfplumber
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List
from backend.app.constants import EMPLOYER_MICROSOFT, EMPLOYER_U_OF_UTAH, EMPLOYER_UNKNOWN

def sha256(p: Path) -> str:
    """Calculate SHA256 hash of a file."""
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

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


def extract_pdf_text_left_half(pdf_path: Path, max_pages: int = 2, x_threshold: float = 320.0) -> str:
    """
    Extract text from the left half of the PDF only.
    
    Microsoft paystubs have a two-column layout where:
    - Left half (x < ~320): Earnings, deductions, taxes data
    - Right half (x >= ~320): Summary info like "Federal taxable wages"
    
    By extracting only the left half, we avoid interference from right-side
    values being concatenated on the same line as left-side data.
    
    Args:
        pdf_path: Path to the PDF file
        max_pages: Maximum number of pages to extract
        x_threshold: X coordinate threshold to separate left/right (default 320 for 612-wide pages)
    
    Returns:
        Extracted text from left half only, with lines reconstructed from characters
    """
    all_lines: List[str] = []
    
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages[:max_pages]:
            # Get all characters with positions
            chars = page.chars
            if not chars:
                continue
            
            # Group characters by Y position (line), filtering to left half only
            lines_dict: Dict[float, List[Tuple[float, str]]] = {}
            for char in chars:
                if char.get('text') and char['x0'] < x_threshold:
                    # Round Y to group characters on same line
                    top = round(char['top'], 0)
                    if top not in lines_dict:
                        lines_dict[top] = []
                    lines_dict[top].append((char['x0'], char['text']))
            
            # Build text lines from characters, sorted by Y then X
            for top in sorted(lines_dict.keys()):
                char_list = lines_dict[top]
                char_list.sort(key=lambda x: x[0])
                
                # Reconstruct line with spacing based on x gaps
                line_chars = []
                prev_x = None
                for x, text in char_list:
                    # Add space if there's a significant gap (> 5 points)
                    if prev_x is not None and (x - prev_x) > 5:
                        line_chars.append(' ')
                    line_chars.append(text)
                    prev_x = x + 4  # Approximate char width
                
                line = ''.join(line_chars).strip()
                if line:
                    all_lines.append(line)
    
    return "\n".join(all_lines)
