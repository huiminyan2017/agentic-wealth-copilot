"""Wealth node — loads wealth.json, computes net worth, synthesizes reply with LLM."""

from __future__ import annotations

import json
from pathlib import Path

from agents.state import CopilotState
from agents import llm
from agents.llm import config_error_reply

_PARSED_DIR = Path(__file__).parent.parent.parent / "data" / "parsed"


def _load_wealth(person: str) -> dict | None:
    path = _PARSED_DIR / person / "wealth.json"
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def _net_worth(w: dict) -> float:
    c = w.get("current", {})
    return (
        c.get("cash", 0)
        + c.get("primary_property", 0)
        + c.get("investment_properties", 0)
        + c.get("stock_value", 0)
        + c.get("retirement_401k", 0)
    )


def _fmt(v: float) -> str:
    return f"${v:,.0f}"


def wealth_node(state: CopilotState) -> CopilotState:
    people: dict[str, dict] = {}
    if _PARSED_DIR.exists():
        for d in sorted(_PARSED_DIR.iterdir()):
            if d.is_dir():
                w = _load_wealth(d.name)
                if w:
                    people[d.name] = w

    if not people:
        state.reply = "No wealth data found. Add a `wealth.json` file under `data/parsed/<person>/`."
        state.trace.append("wealth:no_data")
        return state

    rows: list[tuple[str, dict, float]] = []
    for name, w in people.items():
        rows.append((name, w.get("current", {}), _net_worth(w)))

    lines = ["## Wealth Summary\n"]
    lines.append("| Person | Cash | Property | Stocks | 401k | **Net Worth** |")
    lines.append("|--------|------|----------|--------|------|---------------|")
    for name, c, nw in rows:
        lines.append(
            f"| {name} "
            f"| {_fmt(c.get('cash', 0))} "
            f"| {_fmt(c.get('primary_property', 0))} "
            f"| {_fmt(c.get('stock_value', 0))} "
            f"| {_fmt(c.get('retirement_401k', 0))} "
            f"| **{_fmt(nw)}** |"
        )

    if len(rows) >= 2:
        lines.append("\n### Differences\n")
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                a_name, a_c, a_nw = rows[i]
                b_name, b_c, b_nw = rows[j]
                diff = a_nw - b_nw
                sign = "+" if diff >= 0 else ""
                lines.append(
                    f"**{a_name} vs {b_name}:** "
                    f"{a_name} net worth is {sign}{_fmt(diff)} "
                    f"({'more' if diff >= 0 else 'less'} than {b_name})"
                )
                for label, key in [
                    ("Cash", "cash"),
                    ("Property (share)", "primary_property"),
                    ("Stocks", "stock_value"),
                    ("401k", "retirement_401k"),
                ]:
                    d = a_c.get(key, 0) - b_c.get(key, 0)
                    if abs(d) > 0:
                        sign = "+" if d >= 0 else ""
                        lines.append(f"  - {label}: {sign}{_fmt(d)}")

    targets_lines = []
    for name, w, nw in rows:
        t = w.get("targets", {})
        t401k = t.get("target_401k", 0)
        tnr = t.get("target_non_retirement", 0)
        if t401k or tnr:
            c = w.get("current", {})
            gap401k = t401k - c.get("retirement_401k", 0)
            targets_lines.append(
                f"**{name}** — 401k: {_fmt(c.get('retirement_401k',0))} / {_fmt(t401k)} "
                f"(gap: {_fmt(gap401k)})"
            )
    if targets_lines:
        lines.append("\n### Progress to Targets\n")
        lines.extend(targets_lines)

    data_summary = "\n".join(lines)
    llm_reply = llm.chat([
        {
            "role": "system",
            "content": (
                "You are a helpful personal financial advisor. "
                "The user has asked a question about wealth. "
                "You have computed structured wealth data shown below. "
                "Answer the user's specific question conversationally and concisely, "
                "referencing the numbers. Include the data table as-is, then add your commentary."
            ),
        },
        {
            "role": "user",
            "content": f"User question: {state.user_message}\n\nComputed wealth data:\n{data_summary}",
        },
    ])
    state.reply = llm_reply if llm_reply else config_error_reply()
    state.trace.append(f"wealth:ok:{','.join(people.keys())}")
    return state
