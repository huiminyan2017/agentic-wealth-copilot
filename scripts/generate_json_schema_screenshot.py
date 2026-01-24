"""
Generate static schema screenshots for the demo slide deck:

  05_parsed_json_schema.png  — parsed paystub (data/parsed/.../paystub/*.json)
  06_parsed_w2_schema.png    — parsed W-2     (data/parsed/.../w2/*.json)

Both images use the same VS-Code-dark style: Monokai syntax highlighting,
sidebar with colour-coded schema section annotations, employer badges in the
header showing the schema is shared across all employers.

Usage:
    .venv/bin/python scripts/generate_json_schema_screenshot.py
"""

from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from typing import NamedTuple

from pygments import highlight
from pygments.lexers import JsonLexer
from pygments.formatters import ImageFormatter
from pygments.styles import get_style_by_name
from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = Path(__file__).parent.parent


class Section(NamedTuple):
    label: str
    line_start: int
    line_end: int
    color: str
    desc: str


# ── paystub schema annotations (line numbers in pretty-printed JSON) ──────────
PAYSTUB_SECTIONS: list[Section] = [
    Section("pay_date / employer_name",  2,  4, "#4ec9b0", "Metadata"),
    Section("gross",                      5, 14, "#dcdcaa", "Gross pay + breakdown\n  base · stock · perks\n  bonus · vacation · SSB"),
    Section("pretax_deductions",         15, 22, "#f14c4c", "Pre-tax deductions\n  401k · HSA · FSA"),
    Section("taxes",                     23, 30, "#ce9178", "Withholding taxes\n  federal · SS · Medicare\n  state"),
    Section("aftertax_deductions",       31, 42, "#c586c0", "After-tax deductions\n  Roth 401k · ESPP\n  insurance · giving"),
    Section("net_pay",                   43, 47, "#4fc1ff", "Net take-home pay"),
    Section("stock_pay",                 48, 53, "#b5cea8", "RSU/stock event\n  gross income + tax"),
    Section("validation",                54, 60, "#6a9955", "Invariant checks\n  Σ lines = total (diff=0)"),
    Section("ytd",                       61, 70, "#ffcc02", "Year-to-date accumulators\n  gross · net · taxes"),
]

# ── W-2 schema annotations ────────────────────────────────────────────────────
W2_SECTIONS: list[Section] = [
    Section("year / employer_name",       2,  3, "#4ec9b0", "Metadata"),
    Section("wages",                       4,  4, "#dcdcaa", "Total W-2 wages (Box 1)"),
    Section("federal_tax_withheld",        5,  5, "#f14c4c", "Federal income tax (Box 2)"),
    Section("ss_wages / ss_tax",           6,  7, "#ce9178", "Social Security\n  wages capped @ $128,400\n  tax = wages × 6.2%"),
    Section("medicare_wages / tax",        8,  9, "#c586c0", "Medicare\n  wages · tax = wages × 1.45%"),
    Section("state_wages / tax",          10, 11, "#4fc1ff", "State income\n  wages + withholding"),
    Section("box12_401k_pretax",          12, 12, "#b5cea8", "Box 12 — pre-tax 401k (D)"),
    Section("box12_hsa",                  13, 13, "#6a9955", "Box 12 — HSA employer (W)"),
    Section("box12_roth_401k",            14, 14, "#ffcc02", "Box 12 — Roth 401k (AA)"),
    Section("box12_gtl",                  15, 15, "#d7ba7d", "Box 12 — group term life (C)"),
    Section("missing_fields / warnings",  16, 17, "#888888", "Parse quality flags"),
    Section("source / notes",             18, 20, "#569cd6", "Provenance — PDF path\n  + parser notes"),
]


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    for p in (
        f"/System/Library/Fonts/{name}.ttc",
        f"/System/Library/Fonts/{name}.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ):
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass
    return ImageFont.load_default()


def _render(
    json_path: Path,
    out_path: Path,
    title: str,
    subtitle: str,
    demo_label: str,
    footer_path: str,
    footer_meta: str,
    sections: list[Section],
    sidebar_w: int = 280,
) -> None:
    # 1. Pretty-print JSON
    pretty = json.dumps(json.loads(json_path.read_text()), indent=2)

    # 2. Pygments syntax-highlighted code image
    style = get_style_by_name("monokai")
    fmt = ImageFormatter(
        style=style,
        font_name="Courier New",
        font_size=18,
        line_numbers=True,
        line_number_bg="#1e1e1e",
        line_number_fg="#888888",
        line_pad=3,
        image_pad=20,
    )
    code_img = Image.open(BytesIO(highlight(pretty, JsonLexer(), fmt)))

    # 3. Canvas
    W       = code_img.width
    HDR_H   = 96
    FTR_H   = 54
    TOTAL_W = W + sidebar_w
    TOTAL_H = HDR_H + code_img.height + FTR_H

    canvas = Image.new("RGB", (TOTAL_W, TOTAL_H), "#1e1e1e")
    draw   = ImageDraw.Draw(canvas)

    # header / footer bars
    draw.rectangle([0, 0,                       TOTAL_W, HDR_H],                          fill="#252526")
    draw.line(     [0, HDR_H - 1,               TOTAL_W, HDR_H - 1],                      fill="#0078d4", width=3)
    draw.rectangle([0, HDR_H + code_img.height, TOTAL_W, TOTAL_H],                        fill="#252526")
    draw.line(     [0, HDR_H + code_img.height, TOTAL_W, HDR_H + code_img.height],        fill="#333333", width=1)

    # sidebar
    draw.rectangle([W, HDR_H, TOTAL_W, HDR_H + code_img.height], fill="#1a1a2e")
    draw.line(     [W, HDR_H, W,        HDR_H + code_img.height], fill="#333366", width=2)

    canvas.paste(code_img, (0, HDR_H))

    # 4. Fonts
    f_title = _font("Helvetica",     22)
    f_sub   = _font("Helvetica",     14)
    f_body  = _font("Helvetica",     13)
    f_badge = _font("Helvetica",     12)
    f_label = _font("HelveticaNeue", 15)
    draw    = ImageDraw.Draw(canvas)

    # 5. Header text
    draw.text((24, 14), title,       font=f_title, fill="#ffffff")
    draw.text((24, 44), subtitle,    font=f_sub,   fill="#9cdcfe")
    draw.text((24, 64), demo_label,  font=f_body,  fill="#6a9955")

    # employer badges
    bx = TOTAL_W - 320
    draw.rounded_rectangle([bx,       18, bx + 100, 40], radius=4, fill="#0078d4")
    draw.text((bx + 10,  22), "🏢 Microsoft",     font=f_badge, fill="#ffffff")
    draw.rounded_rectangle([bx + 112, 18, bx + 238, 40], radius=4, fill="#cc5500")
    draw.text((bx + 122, 22), "🎓 Univ. of Utah", font=f_badge, fill="#ffffff")
    draw.rounded_rectangle([bx + 250, 18, bx + 320, 40], radius=4, fill="#444444")
    draw.text((bx + 260, 22), "+ others",          font=f_badge, fill="#aaaaaa")

    # 6. Sidebar section annotations
    total_lines = pretty.count("\n") + 1
    line_h      = code_img.height / total_lines
    SX          = W + 16

    for sec in sections:
        y_top    = HDR_H + int((sec.line_start - 1) * line_h)
        y_bottom = HDR_H + int(sec.line_end * line_h)
        draw.rectangle([W + 4, y_top + 4, W + 7, y_bottom - 4], fill=sec.color)
        draw.text((SX + 14, y_top + 5), sec.label, font=f_label, fill=sec.color)
        for i, line in enumerate(sec.desc.split("\n")):
            draw.text((SX + 14, y_top + 24 + i * 16), line, font=f_body, fill="#aaaaaa")

    # 7. Footer
    FY = HDR_H + code_img.height + 14
    draw.text((24, FY),      f"📂  {footer_path}", font=f_body, fill="#6a9955")
    draw.text((24, FY + 20), footer_meta,           font=f_body, fill="#555555")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(str(out_path), "PNG")
    print(f"✅  {out_path}  ({canvas.width}×{canvas.height} px)")


def generate_paystub() -> None:
    _render(
        json_path   = REPO_ROOT / "data/parsed/DemoMicrosoftEmployee/paystub/2018-04-15_5dce3ac1.json",
        out_path    = REPO_ROOT / "demo/screenshots/05_parsed_json_schema.png",
        title       = "Parsed Paystub Schema",
        subtitle    = "data/parsed/{person}/paystub/*.json  ·  unified format — same schema for all employers",
        demo_label  = "DemoMicrosoftEmployee  ·  2018-04-15",
        footer_path = "data/parsed/DemoMicrosoftEmployee/paystub/2018-04-15_5dce3ac1.json",
        footer_meta = "parser: msft  ·  validation diffs all 0.0  ·  raw_values: {}  ·  warnings: []",
        sections    = PAYSTUB_SECTIONS,
        sidebar_w   = 260,
    )


def generate_w2() -> None:
    _render(
        json_path   = REPO_ROOT / "data/parsed/DemoMicrosoftEmployee/w2/2018_453af4b0.json",
        out_path    = REPO_ROOT / "demo/screenshots/06_parsed_w2_schema.png",
        title       = "Parsed W-2 Schema",
        subtitle    = "data/parsed/{person}/w2/*.json  ·  unified format — same schema for all employers",
        demo_label  = "DemoMicrosoftEmployee  ·  tax year 2018",
        footer_path = "data/parsed/DemoMicrosoftEmployee/w2/2018_453af4b0.json",
        footer_meta = "parser: msft_w2  ·  missing_fields: []  ·  warnings: []",
        sections    = W2_SECTIONS,
        sidebar_w   = 280,
    )


if __name__ == "__main__":
    generate_paystub()
    generate_w2()
