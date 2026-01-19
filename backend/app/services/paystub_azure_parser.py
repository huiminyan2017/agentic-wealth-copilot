"""
Azure-first Microsoft ADP Paystub Parser (Table + Layout + Fallback)

This module implements a robust paystub parser using **Azure AI Document Intelligence**
(prebuilt-layout model) as the default extraction engine.

Why this exists
---------------
Microsoft paystubs come in multiple PDF templates (old/new), and the same template can
extract differently depending on how text is embedded. Regex + pdfplumber breaks easily
because paystubs are **layout-heavy documents** (tables, multi-column grids, side panels).

Azure Document Intelligence gives us **layout primitives**:
- Tables / cells with row/col indices
- Paragraph blocks
- Bounding boxes (spatial coordinates)
It does NOT give semantic meaning (e.g. “this is gross pay”), so we add a mapping layer.

Extraction strategy (in priority order)
---------------------------------------
1) Column-aware table logic (best)
   - If Azure returns a real table with headers like CURRENT / YEAR-TO-DATE (YTD),
     we bind values to roles by detecting those headers.
   - This prevents the classic bug: swapping current vs YTD.

   Example layout:
   | Description        | Current      | Year-to-Date |
   |--------------------|--------------|--------------|
   | Gross Pay          | 7,329.55     | 97,872.38   |
   | Federal Tax        | 1,002.83     | 19,200.45   |
   | Net Pay            | 3,524.70     | 48,300.12   |

   Azure returns this as:
   (row=0)  Description | Current | Year-to-Date
   (row=1)  Gross Pay   | 7,329.55| 97,872.38
   (row=2)  Federal Tax | 1,002.83| 19,200.45
   (row=3)  Net Pay     | 3,524.70| 48,300.12

   How Column-aware logic works
     We detect the meaning of columns from headers:
        Column 0 = label
        Column 1 = current
        Column 2 = ytd
    Then for each row:
        Gross Pay → current=7,329.55, ytd=97,872.38
        Federal Tax → current=1,002.83, ytd=19,200.45
        Net Pay → current=3,524.70, ytd=48,300.12

    Why this is the best case
        Because:
        ✅ Very reliable
        ✅ No guessing
        ✅ No spatial tricks
        ✅ No heuristics
        ✅ No swapping bugs
        This is what spreadsheets look like.

2) Layout pairing (good fallback)
   - Some tables are multi-column label/value grids or have missing headers.
   - Azure may output labels and values in different rows/cols (still structured), so
     we use **bounding-box proximity** to pair:
       label cell -> nearest money cells to the right/below
   - Produces (current, ytd) candidates even when headers are absent.

   Example:
    Gross Pay           7,329.55      97,872.38
    Federal Tax         1,002.83      19,200.45
    Net Pay             3,524.70      48,300.12
    No headers. No column labels.

    Azure might output:
        (row=10, col=0) Gross Pay
        (row=10, col=3) 7,329.55
        (row=10, col=5) 97,872.38

        (row=11, col=0) Federal Tax
        (row=11, col=3) 1,002.83
        (row=11, col=5) 19,200.45

    Instead of using columns, we use geometry:
    We do:
        For each label cell, find the closest money cells.
        ┌─────────────┐     ┌──────────┐    ┌──────────┐
        │ Gross Pay   │ ──▶ │ 7,329.55 │ ─▶ │ 97,872.38│
        └─────────────┘     └──────────┘    └──────────┘
             label            current           ytd

3) Paragraph fallback (last resort, targeted)
   - Old MSFT format sometimes shows taxable wages as text blocks:
       “Federal taxable wages for the period: …”
       “Federal taxable wages for the year: …”
   - If table+layout pairing can’t find taxable wages, we parse these from paragraphs.

Notes
-----
- We also compute pre-tax / post-tax deductions by summing known deduction rows when available.
- We attach "SOURCES" metadata inside `notes` so you can debug where each value came from
  without changing the Pydantic schema.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import hypot
from pathlib import Path
import json
import re
import os
from typing import Any

from backend.app.schemas import PaystubRecord
from backend.app.services.azure_docint import analyze_layout
from backend.app.services.storage import debug_dir
import logging

logger = logging.getLogger(__name__)

DEBUG_LAYOUT = os.getenv("AZURE_DEBUG_LAYOUT", "false").lower() == "true"


def _write_debug_artifact(person: str, pdf_path: Path, payload: dict):
    if not DEBUG_LAYOUT:
        return

    out_dir = debug_dir(person=person)
    out_dir.mkdir(parents=True, exist_ok=True)

    out = out_dir / f"{pdf_path.stem}.debug.json"
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), "utf-8")

    logger.info(f"Wrote visual debug artifact: {out}")

# ---------------------------
# Basic helpers
# ---------------------------

def _norm(s: str) -> str:
    s = (s or "").strip().lower()
    s = s.replace("\u2013", "-").replace("\u2014", "-")
    s = re.sub(r"[\(\)\[\]\{\}]", " ", s)
    s = re.sub(r"[^a-z0-9\-\s/]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _infer_date_from_filename(name: str) -> date | None:
    m = re.search(r"(20\d{2})[-_](\d{2})[-_](\d{2})", name)
    if not m:
        return None
    yyyy, mm, dd = map(int, m.groups())
    try:
        return date(yyyy, mm, dd)
    except Exception:
        return None


def _infer_date_from_text(text: str) -> date | None:
    for pat in [
        r"\bPay\s*Date\b[:\s]*([0-9]{2})/([0-9]{2})/([0-9]{4})",
        r"\bAdvice\s*Date\b[:\s]*([0-9]{2})/([0-9]{2})/([0-9]{4})",
        r"\bCheck\s*Date\b[:\s]*([0-9]{2})/([0-9]{2})/([0-9]{4})",
    ]:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            mm, dd, yyyy = m.groups()
            try:
                return date(int(yyyy), int(mm), int(dd))
            except Exception:
                pass
    return None


def _is_money_like(s: str) -> bool:
    s = (s or "").strip()
    if not s:
        return False
    return bool(
        re.fullmatch(r"-?\$?\d[\d,]*\.\d{2}-?", s)
        or re.fullmatch(r"\(\$?\d[\d,]*\.\d{2}\)", s)
    )


def _to_float_money(s: str | None) -> float | None:
    if not s:
        return None
    ss = s.strip()
    neg = False
    if ss.startswith("(") and ss.endswith(")"):
        neg = True
        ss = ss[1:-1].strip()

    ss = ss.replace("$", "").replace(",", "").strip()

    # trailing minus like "977.09-"
    if ss.endswith("-"):
        neg = True
        ss = ss[:-1].strip()

    try:
        v = float(ss)
        return -v if neg else v
    except Exception:
        return None


def _token_set(s: str) -> set[str]:
    return set(_norm(s).split())


def _token_score(a: str, b: str) -> float:
    A = _token_set(a)
    B = _token_set(b)
    if not A or not B:
        return 0.0
    inter = len(A & B)
    union = len(A | B)
    return inter / union


# ---------------------------
# Bounding box helpers
# ---------------------------

def _polygon_to_bbox(poly):
    """
    Converts Azure polygon into (xmin, ymin, xmax, ymax).
    Azure gives polygons as: [x1, y1, x2, y2, x3, y3, x4, y4]
    """
    if not poly or len(poly) < 8:
        return None

    xs = [float(x) for x in poly[0::2]]
    ys = [float(y) for y in poly[1::2]]

    return {
        "xmin": min(xs),
        "ymin": min(ys),
        "xmax": max(xs),
        "ymax": max(ys),
    }


# def _center(bbox: tuple[float, float, float, float] | None) -> tuple[float, float] | None:
#     if not bbox:
#         return None
#     x1, y1, x2, y2 = bbox
#     return ((x1 + x2) / 2, (y1 + y2) / 2)

def _center(bbox):
    try:
        return (
            (float(bbox["xmin"]) + float(bbox["xmax"])) / 2,
            (float(bbox["ymin"]) + float(bbox["ymax"])) / 2,
        )
    except Exception:
        return None


def _dist(a: tuple[float, float] | None, b: tuple[float, float] | None) -> float:
    if not a or not b:
        return float("inf")
    return hypot(a[0] - b[0], a[1] - b[1])


# ---------------------------
# Canonical label phrases (semantic mapping)
# ---------------------------

CANONICAL_LABELS: dict[str, list[str]] = {
    # earnings
    "gross_pay": ["gross pay", "total earnings", "gross wages"],
    "taxable_wages": ["taxable earnings", "taxable wages", "federal taxable wages"],

    # taxes
    "federal_tax": ["federal income tax", "federal tax", "fed income tax"],
    "ss_tax": ["social security tax", "fica ss", "ss tax"],
    "medicare_tax": ["medicare tax", "fica medicare"],
    "state_tax": ["withholding - utah", "withholding utah", "ut w/h tax", "state income tax", "state tax"],

    # net
    "net_pay": ["net pay", "take home pay", "net amount"],

    # deductions (optional)
    "pre401k": ["401k (pre-tax)", "401k pre-tax", "401k pre tax", "401k pretax"],
    "hsa": ["hsa employee cont", "hsa ee contribution", "hsa contribution"],
    "after401k": ["401k (after-tax)", "401k after-tax", "401k after tax"],
    "roth": ["roth (after-tax)", "401k roth", "roth after tax", "roth"],
    "espp": ["espp"],
}


# ---------------------------
# Table row model (from Azure tables)
# ---------------------------

@dataclass
class RowVals:
    label: str
    current: float | None
    ytd: float | None
    label_row: int
    src_table: int


@dataclass
class CellBox:
    text: str
    row: int
    col: int
    bbox: tuple[float, float, float, float] | None
    table_id: int


def _detect_column_roles_from_table_text(grid_text: dict[tuple[int, int], str], max_r: int, max_c: int) -> dict[int, str]:
    """
    Infer which columns are CURRENT vs YTD from headers.
    Returns {col_index: "current"|"ytd"}.
    """
    col_role: dict[int, str] = {}
    header_rows = list(range(0, min(5, max_r + 1)))

    for c in range(max_c + 1):
        parts = []
        for r in header_rows:
            t = (grid_text.get((r, c), "") or "").strip()
            if t:
                parts.append(t)
        header = _norm(" ".join(parts))

        if any(k in header for k in ["this period", "current"]):
            col_role[c] = "current"
        if any(k in header for k in ["year-to-date", "year to date", "ytd"]):
            col_role[c] = "ytd"

    return col_role


def _extract_rows_from_tables(result: Any) -> tuple[list[RowVals], list[str], list[CellBox]]:
    """
    Extract (label, current, ytd) rows from Azure tables.
    Also return flat cells with bounding boxes for layout pairing.
    """
    warnings: list[str] = []
    rows: list[RowVals] = []
    flat_cells: list[CellBox] = []

    tables = getattr(result, "tables", None) or []

    for ti, t in enumerate(tables):
        # grid[(r,c)] = {"text":..., "bbox":...}
        grid: dict[tuple[int, int], dict[str, Any]] = {}
        max_r = 0
        max_c = 0

        for cell in t.cells:
            r = cell.row_index
            c = cell.column_index
            txt = (cell.content or "").strip()

            bbox = None
            if getattr(cell, "bounding_regions", None):
                try:
                    bbox = _polygon_to_bbox(cell.bounding_regions[0].polygon)
                except Exception:
                    bbox = None

            if txt:
                grid[(r, c)] = {"text": txt, "bbox": bbox}
                flat_cells.append(CellBox(text=txt, row=r, col=c, bbox=bbox, table_id=ti))

            max_r = max(max_r, r)
            max_c = max(max_c, c)

        grid_text = {k: v["text"] for k, v in grid.items()}
        col_roles = _detect_column_roles_from_table_text(grid_text, max_r, max_c)

        # parse each row into RowVals
        for r in range(max_r + 1):
            cells = [grid.get((r, c), {}).get("text", "").strip() for c in range(max_c + 1)]
            if not any(cells):
                continue

            # identify row label
            label = ""
            for ctext in cells:
                if not ctext:
                    continue
                if _is_money_like(ctext):
                    continue
                cn = _norm(ctext)
                if cn in {"current", "year-to-date", "year to date", "description", "rate", "hours", "amount", "total"}:
                    continue
                label = ctext
                break

            if not label:
                continue

            current = None
            ytd = None

            # Column-aware extraction if roles exist
            if col_roles:
                for c in range(max_c + 1):
                    role = col_roles.get(c)
                    if role not in ("current", "ytd"):
                        continue
                    vtxt = cells[c]
                    if _is_money_like(vtxt):
                        v = _to_float_money(vtxt)
                        if v is None:
                            continue
                        if role == "current":
                            current = v
                        else:
                            ytd = v

            # Heuristic fallback if we couldn't assign anything
            if current is None and ytd is None:
                mvals: list[float] = []
                for ctext in cells:
                    if _is_money_like(ctext):
                        v = _to_float_money(ctext)
                        if v is not None:
                            mvals.append(v)
                if len(mvals) >= 2:
                    current, ytd = mvals[-2], mvals[-1]
                elif len(mvals) == 1:
                    current = mvals[0]

                if not col_roles:
                    warnings.append(f"Could not infer CURRENT/YTD columns for table {ti}; used heuristic mapping.")

            rows.append(RowVals(label=label, current=current, ytd=ytd, label_row=r, src_table=ti))

    return rows, warnings, flat_cells


# ---------------------------
# Layout pairing engine (label -> nearest money values)
# ---------------------------

def _looks_like_label(s: str) -> bool:
    if not s:
        return False
    s = s.strip()
    if _is_money_like(s):
        return False
    # avoid pure numeric/ID values
    if re.fullmatch(r"[0-9\-/\.]+", s):
        return False
    # typical label: alphabetic + spaces
    if re.search(r"[A-Za-z]", s) and len(s) >= 3:
        return True
    return False


@dataclass
class PairVals:
    label: str
    current: float | None
    ytd: float | None
    score: float


def _pair_labels_to_money_values(flat_cells: list[CellBox]) -> list[PairVals]:
    """
    For each label-like cell, find nearby money-like cells using bbox geometry.

    We prefer:
    - money to the RIGHT on the same row band (best)
    - money BELOW in same column band (secondary)
    - nearest by distance (last fallback)

    If we find multiple money candidates to the right, we interpret:
      first = current, second = ytd (common in earnings/tax rows),
    but if only one exists we set current only.
    """
    # Partition into labels and money cells
    labels = [c for c in flat_cells if _looks_like_label(c.text)]
    monies = [c for c in flat_cells if _is_money_like(c.text)]

    out: list[PairVals] = []

    for lab in labels:
        lc = _center(lab.bbox)

        # candidate money cells
        right_same_row: list[tuple[float, CellBox]] = []
        below_same_col: list[tuple[float, CellBox]] = []
        nearest_any: list[tuple[float, CellBox]] = []

        for m in monies:
            # keep within same table as a strong prior (prevents weird cross-table matches)
            if m.table_id != lab.table_id:
                continue

            mc = _center(m.bbox)
            d = _dist(lc, mc)
            nearest_any.append((d, m))

            # If we have bboxes, use direction heuristics
            if lab.bbox and m.bbox:
                lx1, ly1, lx2, ly2 = lab.bbox
                mx1, my1, mx2, my2 = m.bbox

                # right side: m starts to the right of label end, and overlaps y-band
                y_overlap = not (my2 < ly1 or my1 > ly2)
                if mx1 >= lx2 and y_overlap:
                    right_same_row.append((mx1, m))  # sort by x position

                # below: overlap x-band and below label
                x_overlap = not (mx2 < lx1 or mx1 > lx2)
                if my1 >= ly2 and x_overlap:
                    below_same_col.append((my1, m))  # sort by y

        right_same_row.sort(key=lambda x: x[0])
        below_same_col.sort(key=lambda x: x[0])
        nearest_any.sort(key=lambda x: x[0])

        current = None
        ytd = None
        score = 0.0

        # best: right on same row
        if right_same_row:
            m1 = right_same_row[0][1]
            current = _to_float_money(m1.text)
            score = 0.85
            if len(right_same_row) >= 2:
                m2 = right_same_row[1][1]
                ytd = _to_float_money(m2.text)
                score = 0.92

        # fallback: below in same col band
        elif below_same_col:
            m1 = below_same_col[0][1]
            current = _to_float_money(m1.text)
            score = 0.70
            if len(below_same_col) >= 2:
                m2 = below_same_col[1][1]
                ytd = _to_float_money(m2.text)
                score = 0.78

        # last: nearest
        elif nearest_any:
            m1 = nearest_any[0][1]
            current = _to_float_money(m1.text)
            score = 0.55

        if current is not None or ytd is not None:
            out.append(PairVals(label=lab.text, current=current, ytd=ytd, score=score))

    return out


def _lookup_from_pairs(pairs: list[PairVals], phrases: list[str], min_score: float = 0.35) -> tuple[float | None, float | None, float]:
    """
    Find best-matching PairVals label against phrases, return (current, ytd, label_score).
    """
    best = None
    best_score = 0.0
    for pv in pairs:
        for p in phrases:
            s = _token_score(pv.label, p)
            if s > best_score:
                best_score = s
                best = pv
    if not best or best_score < min_score:
        return None, None, best_score
    return best.current, best.ytd, best_score


# ---------------------------
# Paragraph fallback (targeted)
# ---------------------------

def _find_taxable_wages_in_paragraphs(full_text: str) -> tuple[float | None, float | None]:
    """
    Old MSFT format often includes:
      Federal taxable wages for the period: <money>
      Federal taxable wages for the year: <money>

    We use bounded patterns (limited drift) to avoid grabbing random numbers.
    """
    t = full_text or ""

    def find_one(kind: str) -> float | None:
        pat = rf"Federal\s+taxable\s+wages[\s\S]{{0,40}}{kind}[\s\S]{{0,40}}([0-9,]+\.\d{{2}})"
        m = re.search(pat, t, re.IGNORECASE)
        if not m:
            return None
        return _to_float_money(m.group(1))

    return find_one("period"), find_one("year")


# ---------------------------
# Semantic mapping from RowVals
# ---------------------------

def _best_match(label: str, target_phrases: list[str]) -> float:
    return max((_token_score(label, p) for p in target_phrases), default=0.0)


def _pick_field(rows: list[RowVals], field: str, min_score: float = 0.55) -> tuple[RowVals | None, float]:
    phrases = CANONICAL_LABELS.get(field, [])
    best: RowVals | None = None
    best_score = 0.0
    for r in rows:
        s = _best_match(r.label, phrases)
        if s > best_score:
            best = r
            best_score = s
    if best is None or best_score < min_score:
        return None, best_score
    return best, best_score


# ---------------------------
# Main entry: parse_paystub_azure
# ---------------------------

def parse_paystub_azure(pdf_path: Path, employer: str, person: str, sha8: str) -> PaystubRecord:
    """
    Parse a paystub using Azure Document Intelligence (layout model).

    Precedence:
      1) Column-aware table rows (RowVals)
      2) Layout pairing (label -> money cells)
      3) Paragraph fallback for taxable wages (old MSFT format)
    """
    result = analyze_layout(pdf_path)

    # Collect paragraphs (for date + taxable fallback)
    paragraphs = getattr(result, "paragraphs", None) or []
    full_text = "\n".join([p.content for p in paragraphs if getattr(p, "content", None)])

    # Extract tables -> rows + flat cells
    rows, table_warnings, flat_cells = _extract_rows_from_tables(result)

    logger.info(f"Azure table extraction produced {len(rows)} rows with {len(table_warnings)} warnings.")

    debug = {
        "file": str(pdf_path),
        "tables": [],
        "flat_cells": [],
        "pairs": [],
        "paragraph_fallbacks": [],
        "final_mapping": {}
    }

    logger.info(f"Beginning semantic mapping for paystub: {pdf_path.name}")
    logger.info("Azure returned %d tables", len(result.tables or []))

    # Dump tables
    try:

        for ti, t in enumerate(getattr(result, "tables", []) or []):
            table_dump = []
            for c in t.cells:
                table_dump.append({
                    "row": c.row_index,
                    "col": c.column_index,
                    "text": c.content,
                    "bbox": _polygon_to_bbox(c.bounding_regions[0].polygon) if c.bounding_regions else None
                })
            debug["tables"].append(table_dump)
    except Exception as e:
        logger.error(f"Error dumping tables for debug: {e}")

    logger.info(f"Dumped {len(debug['tables'])} tables for debugging.")

    # Dump flat cells
    for c in flat_cells:
        debug["flat_cells"].append({
            "text": c.text,
            "row": c.row,
            "col": c.col,
            "bbox": c.bbox,
            "table_id": c.table_id
        })

    logger.info(f"Dumped {len(debug['flat_cells'])} flat cells for debugging.")

    # Layout pairing candidates (label -> current/ytd)

    try:
        pairs = _pair_labels_to_money_values(flat_cells)
        for p in pairs:
            debug["pairs"].append({
                "label": p.label,
                "current": p.current,
                "ytd": p.ytd,
                "confidence": p.score
            })
    except Exception as e:
        logger.error(f"Error during layout pairing: {e}")

    logger.info(f"Layout pairing produced {len(pairs)} label->money pairs.")

    # Field sources for debugging
    field_sources: dict[str, str] = {}

    # --- Pay date ---
    pay_date = _infer_date_from_filename(pdf_path.name) or _infer_date_from_text(full_text) or date.today()

    # --- Primary extraction: table semantic mapping ---
    gross_row, sgross = _pick_field(rows, "gross_pay")
    tax_row, stax = _pick_field(rows, "taxable_wages")
    net_row, snet = _pick_field(rows, "net_pay")

    fed_row, sfed = _pick_field(rows, "federal_tax")
    ss_row, sss = _pick_field(rows, "ss_tax")
    med_row, smed = _pick_field(rows, "medicare_tax")
    state_row, sstate = _pick_field(rows, "state_tax")

    pre401k_row, _ = _pick_field(rows, "pre401k", min_score=0.45)
    hsa_row, _ = _pick_field(rows, "hsa", min_score=0.45)
    after401k_row, _ = _pick_field(rows, "after401k", min_score=0.45)
    roth_row, _ = _pick_field(rows, "roth", min_score=0.45)
    espp_row, _ = _pick_field(rows, "espp", min_score=0.45)

    def row_val(row: RowVals | None) -> tuple[float | None, float | None]:
        if not row:
            return None, None
        return row.current, row.ytd

    gross_cur, gross_ytd = row_val(gross_row)
    tax_cur, tax_ytd = row_val(tax_row)
    net_cur, net_ytd = row_val(net_row)

    fed_cur, fed_ytd = row_val(fed_row)
    ss_cur, ss_ytd = row_val(ss_row)
    med_cur, med_ytd = row_val(med_row)
    state_cur, state_ytd = row_val(state_row)

    if gross_row:
        field_sources["gross_pay"] = f"table:{gross_row.src_table}:{gross_row.label}"
    if tax_row:
        field_sources["taxable_wages"] = f"table:{tax_row.src_table}:{tax_row.label}"
    if net_row:
        field_sources["net_pay"] = f"table:{net_row.src_table}:{net_row.label}"
    if fed_row:
        field_sources["federal_tax"] = f"table:{fed_row.src_table}:{fed_row.label}"
    if ss_row:
        field_sources["ss_tax"] = f"table:{ss_row.src_table}:{ss_row.label}"
    if med_row:
        field_sources["medicare_tax"] = f"table:{med_row.src_table}:{med_row.label}"
    if state_row:
        field_sources["state_tax"] = f"table:{state_row.src_table}:{state_row.label}"

    # --- Secondary extraction: layout pairing fallback ---
    # Use layout pairing if table mapping misses current/ytd.
    def fill_from_pairs(field_key: str, cur: float | None, ytd: float | None) -> tuple[float | None, float | None, float]:
        pcur, pytd, ls = _lookup_from_pairs(pairs, CANONICAL_LABELS.get(field_key, []))
        new_cur = cur if cur is not None else pcur
        new_ytd = ytd if ytd is not None else pytd
        return new_cur, new_ytd, ls

    # gross
    gross_cur, gross_ytd, lgross = fill_from_pairs("gross_pay", gross_cur, gross_ytd)
    if ("gross_pay" not in field_sources) and (gross_cur is not None or gross_ytd is not None):
        field_sources["gross_pay"] = f"layout_pairing(score={lgross:.2f})"

    # taxes & net
    fed_cur, fed_ytd, lfed = fill_from_pairs("federal_tax", fed_cur, fed_ytd)
    if ("federal_tax" not in field_sources) and (fed_cur is not None or fed_ytd is not None):
        field_sources["federal_tax"] = f"layout_pairing(score={lfed:.2f})"

    ss_cur, ss_ytd, lss = fill_from_pairs("ss_tax", ss_cur, ss_ytd)
    if ("ss_tax" not in field_sources) and (ss_cur is not None or ss_ytd is not None):
        field_sources["ss_tax"] = f"layout_pairing(score={lss:.2f})"

    med_cur, med_ytd, lmed = fill_from_pairs("medicare_tax", med_cur, med_ytd)
    if ("medicare_tax" not in field_sources) and (med_cur is not None or med_ytd is not None):
        field_sources["medicare_tax"] = f"layout_pairing(score={lmed:.2f})"

    state_cur, state_ytd, lst = fill_from_pairs("state_tax", state_cur, state_ytd)
    if ("state_tax" not in field_sources) and (state_cur is not None or state_ytd is not None):
        field_sources["state_tax"] = f"layout_pairing(score={lst:.2f})"

    net_cur, net_ytd, lnet = fill_from_pairs("net_pay", net_cur, net_ytd)
    if ("net_pay" not in field_sources) and (net_cur is not None or net_ytd is not None):
        field_sources["net_pay"] = f"layout_pairing(score={lnet:.2f})"

    # taxable wages (table/pairs first, paragraph last)
    tax_cur, tax_ytd, ltax = fill_from_pairs("taxable_wages", tax_cur, tax_ytd)
    if ("taxable_wages" not in field_sources) and (tax_cur is not None or tax_ytd is not None):
        field_sources["taxable_wages"] = f"layout_pairing(score={ltax:.2f})"

    # --- Paragraph fallback for taxable wages (last resort) ---
    if tax_cur is None or tax_ytd is None:
        p_period, p_year = _find_taxable_wages_in_paragraphs(full_text)
        if p_period or p_year:
            debug["paragraph_fallbacks"].append({
                "type": "taxable_wages",
                "period": p_period,
                "year": p_year
            })
        if tax_cur is None and p_period is not None:
            tax_cur = p_period
            field_sources["taxable_wages"] = "paragraph:Federal taxable wages for the period"
        if tax_ytd is None and p_year is not None:
            tax_ytd = p_year
            field_sources["ytd_taxable_wages"] = "paragraph:Federal taxable wages for the year"

    debug["final_mapping"] = field_sources

    # --- Deductions ---
    def abs_money(x: float | None) -> float | None:
        return abs(x) if x is not None else None

    pre_tax_sum = 0.0
    pre_seen = False
    for r in [pre401k_row, hsa_row]:
        if r and r.current is not None:
            pre_tax_sum += abs(r.current)
            pre_seen = True
    pre_tax_deductions = round(pre_tax_sum, 2) if pre_seen else None

    post_tax_sum = 0.0
    post_seen = False
    for r in [after401k_row, roth_row, espp_row]:
        if r and r.current is not None:
            post_tax_sum += abs(r.current)
            post_seen = True
    post_tax_deductions = round(post_tax_sum, 2) if post_seen else None

    # Normalize taxes to positive withheld amounts (paystubs may show negative)
    fed_cur = abs_money(fed_cur)
    fed_ytd = abs_money(fed_ytd)
    ss_cur = abs_money(ss_cur)
    ss_ytd = abs_money(ss_ytd)
    med_cur = abs_money(med_cur)
    med_ytd = abs_money(med_ytd)
    state_cur = abs_money(state_cur)
    state_ytd = abs_money(state_ytd)

    # Build record
    rec = PaystubRecord(
        pay_date=pay_date,
        employer_name=employer,

        gross_pay=gross_cur,
        pre_tax_deductions=pre_tax_deductions,
        post_tax_deductions=post_tax_deductions,

        taxable_wages=tax_cur,
        federal_tax=fed_cur,
        ss_tax=ss_cur,
        medicare_tax=med_cur,
        state_tax=state_cur,
        other_taxes=0.0,
        net_pay=net_cur,

        ytd_gross=gross_ytd,
        ytd_taxable_wages=tax_ytd,
        ytd_federal_tax=fed_ytd,
        ytd_state_tax=state_ytd,
        ytd_ss_tax=ss_ytd,
        ytd_medicare_tax=med_ytd,

        extracted_text_path=None,
        source_pdf_relpath=str(pdf_path),
        notes="Parsed with Azure Document Intelligence (column-aware + layout pairing + paragraph fallback)",
    )

    # Ensure list fields exist even if schema defaults change
    if rec.warnings is None:
        rec.warnings = []
    if rec.missing_fields is None:
        rec.missing_fields = []

    # Warnings
    rec.warnings.extend(table_warnings)

    # Confidence hints (table mapping)
    confidences = {
        "gross_pay": sgross,
        "taxable_wages": stax,
        "net_pay": snet,
        "federal_tax": sfed,
        "ss_tax": sss,
        "medicare_tax": smed,
        "state_tax": sstate,
    }
    low = {k: v for k, v in confidences.items() if v < 0.65}
    if low:
        rec.warnings.append(
            "Low-confidence table label mapping: " + ", ".join([f"{k}={v:.2f}" for k, v in sorted(low.items())])
        )

    # Missing core fields
    core = ["gross_pay", "taxable_wages", "net_pay"]
    rec.missing_fields = [f for f in core if getattr(rec, f) is None]
    if rec.missing_fields:
        rec.warnings.append("Azure parse missing core fields: " + ", ".join(rec.missing_fields))

    # Attach sources into notes for debugging
    try:
        src_note = json.dumps({"field_sources": field_sources}, ensure_ascii=False)
        rec.notes = (rec.notes or "") + f"\nSOURCES: {src_note}"
    except Exception:
        pass

    logger.info(f"Azure parse results: gross={rec.gross_pay}, net={rec.net_pay}, federal_tax={rec.federal_tax}, pay_date={rec.pay_date}")
    _write_debug_artifact(person, pdf_path, debug)
    return rec