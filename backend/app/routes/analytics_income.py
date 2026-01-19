from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pathlib import Path
from datetime import date, datetime
import json
from collections import defaultdict

from backend.app.services.storage import parsed_dir

router = APIRouter()

def _load_paystubs(person: str) -> list[dict]:
    pdir = parsed_dir(person) / "paystub"
    if not pdir.exists():
        return []
    out = []
    for fp in sorted(pdir.glob("*.json")):
        try:
            out.append(json.loads(fp.read_text("utf-8")))
        except Exception:
            continue
    return out

def _parse_date(d) -> date | None:
    if d is None:
        return None
    if isinstance(d, date):
        return d
    if isinstance(d, str):
        # pydantic dumps dates as "YYYY-MM-DD"
        try:
            return datetime.strptime(d[:10], "%Y-%m-%d").date()
        except Exception:
            return None
    return None

def _f(x):
    try:
        return float(x) if x is not None else None
    except Exception:
        return None

@router.get("/income/trends")
def income_trends(person: str):
    """
    Returns monthly time series for gross/net/taxes/deductions, plus simple insights.
    Reads from data/parsed/<person>/paystub/*.json
    """
    records = _load_paystubs(person)
    if not records:
        raise HTTPException(status_code=404, detail=f"No parsed paystubs found for {person}")

    monthly = defaultdict(lambda: {
        "paychecks": 0,
        "gross": 0.0,
        "net": 0.0,
        "federal_tax": 0.0,
        "state_tax": 0.0,
        "ss_tax": 0.0,
        "medicare_tax": 0.0,
        "pre_tax_deductions": 0.0,
        "post_tax_deductions": 0.0,
        "missing_core_fields": 0,
    })

    # core fields we care about for “data quality”
    core_fields = ["gross_pay", "net_pay", "federal_tax", "state_tax", "ss_tax", "medicare_tax"]

    for r in records:
        pd = _parse_date(r.get("pay_date"))
        if pd is None:
            continue
        month_key = f"{pd.year:04d}-{pd.month:02d}"

        m = monthly[month_key]
        m["paychecks"] += 1

        gross = _f(r.get("gross_pay"))
        net = _f(r.get("net_pay"))
        fed = _f(r.get("federal_tax"))
        st = _f(r.get("state_tax"))
        ss = _f(r.get("ss_tax"))
        med = _f(r.get("medicare_tax"))
        pre = _f(r.get("pre_tax_deductions"))
        post = _f(r.get("post_tax_deductions"))

        if gross is not None: m["gross"] += gross
        if net is not None: m["net"] += net
        if fed is not None: m["federal_tax"] += fed
        if st is not None: m["state_tax"] += st
        if ss is not None: m["ss_tax"] += ss
        if med is not None: m["medicare_tax"] += med
        if pre is not None: m["pre_tax_deductions"] += pre
        if post is not None: m["post_tax_deductions"] += post

        # missing counter
        missing = 0
        for f in core_fields:
            if r.get(f) is None:
                missing += 1
        if missing:
            m["missing_core_fields"] += missing

    # sort months
    months = sorted(monthly.keys())

    series = []
    insights = []

    prev_gross = None
    for mk in months:
        m = monthly[mk]
        total_tax = m["federal_tax"] + m["state_tax"] + m["ss_tax"] + m["medicare_tax"]
        eff_tax_rate = (total_tax / m["gross"]) if m["gross"] > 1e-9 else None
        savings_like = ((m["gross"] - total_tax - m["net"]) if (m["gross"] > 0 and m["net"] > 0) else None)

        series.append({
            "month": mk,
            "paychecks": m["paychecks"],
            "gross": round(m["gross"], 2),
            "net": round(m["net"], 2),
            "tax_total": round(total_tax, 2),
            "eff_tax_rate": round(eff_tax_rate, 4) if eff_tax_rate is not None else None,
            "federal_tax": round(m["federal_tax"], 2),
            "state_tax": round(m["state_tax"], 2),
            "ss_tax": round(m["ss_tax"], 2),
            "medicare_tax": round(m["medicare_tax"], 2),
            "pre_tax_deductions": round(m["pre_tax_deductions"], 2),
            "post_tax_deductions": round(m["post_tax_deductions"], 2),
            "missing_core_fields": m["missing_core_fields"],
            "implied_other_outflows": round(savings_like, 2) if savings_like is not None else None,
        })

        # simple insight: large jump/drop in monthly gross
        if prev_gross is not None and m["gross"] > 0 and prev_gross > 0:
            change = (m["gross"] - prev_gross) / prev_gross
            if change >= 0.25:
                insights.append(f"{mk}: Gross income increased by {change*100:.1f}% vs previous month (bonus/RSU/extra pay?)")
            elif change <= -0.25:
                insights.append(f"{mk}: Gross income decreased by {abs(change)*100:.1f}% vs previous month (missing paystub(s) or unpaid leave?)")
        if m["missing_core_fields"] > 0:
            insights.append(f"{mk}: Some paystubs have missing fields (total missing core fields this month: {m['missing_core_fields']}).")

        prev_gross = m["gross"] if m["gross"] > 0 else prev_gross

    return {
        "person": person,
        "months": months,
        "series": series,
        "insights": insights[:20],
    }