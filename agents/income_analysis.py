"""Income analysis pipeline.

Pure data functions + a thin run_income_analysis() entry point.
No LLM calls — all logic is deterministic arithmetic and rule-based checks.

External entry point: run_income_analysis(person) -> dict
Results are cached by (person, file-mtimes) so repeated copilot questions
within the same session don't re-read and re-compute everything.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path

logger = logging.getLogger(__name__)
from typing import Optional

from backend.app.services.paths import parsed_dir


# ── SS wage base limits ───────────────────────────────────────────────────────

SS_WAGE_LIMITS = {
    2018: 128400,
    2019: 132900,
    2020: 137700,
    2021: 142800,
    2022: 147000,
    2023: 160200,
    2024: 168600,
    2025: 176100,
    2026: 180000,
}


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Pure data functions
# ═══════════════════════════════════════════════════════════════════════════════

def load_income_data(person: str) -> dict:
    paystubs = _load_paystubs(person)
    w2s      = _load_w2s(person)
    return {
        "paystubs": paystubs,
        "w2s":      w2s,
        "summary": {
            "paystub_count":  len(paystubs),
            "w2_count":       len(w2s),
            "years_covered":  _get_years_covered(paystubs, w2s),
            "employers":      list(set(p.get("employer_name", "unknown") for p in paystubs)),
        },
    }


def _load_paystubs(person: str) -> list[dict]:
    pdir = parsed_dir(person) / "paystub"
    if not pdir.exists():
        return []
    out = []
    for fp in sorted(pdir.glob("*.json")):
        try:
            out.append(json.loads(fp.read_text("utf-8")))
        except Exception as e:
            logger.warning("Skipping corrupted paystub file %s: %s", fp, e)
    return out


def _load_w2s(person: str) -> list[dict]:
    pdir = parsed_dir(person) / "w2"
    if not pdir.exists():
        return []
    out = []
    for fp in sorted(pdir.glob("*.json")):
        try:
            out.append(json.loads(fp.read_text("utf-8")))
        except Exception as e:
            logger.warning("Skipping corrupted W-2 file %s: %s", fp, e)
    return out


def _get_years_covered(paystubs: list, w2s: list) -> list[int]:
    years: set[int] = set()
    for p in paystubs:
        try:
            years.add(int(str(p.get("pay_date", ""))[:4]))
        except Exception:
            pass
    for w in w2s:
        if w.get("year"):
            years.add(int(w["year"]))
    return sorted(years)


def _get_value(data: dict, key: str) -> Optional[float]:
    val = data.get(key)
    if val is None:
        return None
    if isinstance(val, dict):
        return val.get("value")
    return val


# ── Trends ────────────────────────────────────────────────────────────────────

def compute_trends(paystubs: list, w2s: list) -> dict:
    monthly = _aggregate_monthly(paystubs)
    yearly  = _aggregate_yearly(paystubs, w2s)

    tax_rates = {}
    for year, data in yearly.items():
        if data["gross"] > 0:
            tax_rates[year] = {
                "effective_rate": data["total_tax"] / data["gross"],
                "federal_rate":   data["federal_tax"] / data["gross"],
                "state_rate":     data["state_tax"] / data["gross"],
            }

    years = sorted(yearly.keys())
    growth = {}
    for i in range(1, len(years)):
        prev, curr = years[i - 1], years[i]
        prev_gross = yearly[prev]["gross"]
        curr_gross = yearly[curr]["gross"]
        if prev_gross > 0:
            growth[curr] = {
                "gross_growth": (curr_gross - prev_gross) / prev_gross,
                "gross_change":  curr_gross - prev_gross,
            }

    return {
        "monthly_series":      monthly,
        "yearly_summary":      yearly,
        "effective_tax_rates": tax_rates,
        "income_growth":       growth,
    }


def _aggregate_monthly(paystubs: list) -> list[dict]:
    monthly: dict = defaultdict(lambda: {
        "gross": 0.0, "net": 0.0, "taxes": 0.0,
        "federal_tax": 0.0, "state_tax": 0.0,
        "ss_tax": 0.0, "medicare_tax": 0.0,
        "pretax_deductions": 0.0, "aftertax_deductions": 0.0,
        "stock_income": 0.0, "paychecks": 0,
    })
    for p in paystubs:
        pay_date = p.get("pay_date")
        if not pay_date:
            continue
        m = monthly[str(pay_date)[:7]]
        m["paychecks"] += 1
        m["gross"]               += _get_value(p, "gross") or 0
        m["net"]                 += _get_value(p, "net_pay") or 0
        m["pretax_deductions"]   += abs(_get_value(p, "pretax_deductions") or 0)
        m["aftertax_deductions"] += abs(_get_value(p, "aftertax_deductions") or 0)
        m["stock_income"]        += _get_value(p, "stock_pay") or 0
        taxes = p.get("taxes", {})
        if isinstance(taxes, dict):
            d = taxes.get("details", {})
            m["federal_tax"]  += abs(d.get("federal", 0) or 0)
            m["state_tax"]    += abs(d.get("state", 0) or 0)
            m["ss_tax"]       += abs(d.get("ss", 0) or 0)
            m["medicare_tax"] += abs(d.get("medicare", 0) or 0)
            m["taxes"]        += abs(_get_value(p, "taxes") or 0)

    result = []
    for month in sorted(monthly):
        data = monthly[month]
        data["month"] = month
        data["effective_tax_rate"] = data["taxes"] / data["gross"] if data["gross"] else 0
        result.append(data)
    return result


def _aggregate_yearly(paystubs: list, w2s: list) -> dict[int, dict]:
    yearly: dict = defaultdict(lambda: {
        "gross": 0.0, "net": 0.0, "total_tax": 0.0,
        "federal_tax": 0.0, "state_tax": 0.0,
        "ss_tax": 0.0, "medicare_tax": 0.0,
        "paychecks": 0, "source": "paystub",
    })
    for p in paystubs:
        pay_date = p.get("pay_date")
        if not pay_date:
            continue
        try:
            year = int(str(pay_date)[:4])
        except Exception:
            continue
        y = yearly[year]
        y["paychecks"] += 1
        y["gross"] += _get_value(p, "gross") or 0
        y["net"]   += _get_value(p, "net_pay") or 0
        taxes = p.get("taxes", {})
        if isinstance(taxes, dict):
            d = taxes.get("details", {})
            y["federal_tax"]  += abs(d.get("federal", 0) or 0)
            y["state_tax"]    += abs(d.get("state", 0) or 0)
            y["ss_tax"]       += abs(d.get("ss", 0) or 0)
            y["medicare_tax"] += abs(d.get("medicare", 0) or 0)
        y["total_tax"] = y["federal_tax"] + y["state_tax"] + y["ss_tax"] + y["medicare_tax"]

    for w in w2s:
        year = w.get("year")
        if not year:
            continue
        yearly[year] = {
            "gross":          w.get("wages", 0) or 0,
            "net":            0,
            "total_tax":      sum(w.get(k, 0) or 0 for k in (
                                  "federal_tax_withheld", "state_tax_withheld",
                                  "ss_tax_withheld", "medicare_tax_withheld")),
            "federal_tax":    w.get("federal_tax_withheld", 0) or 0,
            "state_tax":      w.get("state_tax_withheld", 0) or 0,
            "ss_tax":         w.get("ss_tax_withheld", 0) or 0,
            "medicare_tax":   w.get("medicare_tax_withheld", 0) or 0,
            "ss_wages":       w.get("ss_wages", 0) or 0,
            "medicare_wages": w.get("medicare_wages", 0) or 0,
            "paychecks":      yearly[year]["paychecks"],
            "source":         "w2",
        }
    return dict(yearly)


# ── Anomaly detection ─────────────────────────────────────────────────────────

def detect_anomalies(trends: dict, paystubs: list, w2s: list) -> list[dict]:
    anomalies = []
    monthly   = trends.get("monthly_series", [])
    yearly    = trends.get("yearly_summary", {})
    tax_rates = trends.get("effective_tax_rates", {})

    # Tax rate change year-over-year
    years = sorted(tax_rates)
    for i in range(1, len(years)):
        prev, curr = years[i - 1], years[i]
        change = tax_rates[curr]["effective_rate"] - tax_rates[prev]["effective_rate"]
        if abs(change) > 0.03:
            anomalies.append({
                "type": "tax_rate_change",
                "severity": "high" if abs(change) > 0.05 else "medium",
                "year": curr,
                "details": {
                    "previous_rate": tax_rates[prev]["effective_rate"],
                    "current_rate":  tax_rates[curr]["effective_rate"],
                    "change": change,
                },
                "message": (
                    f"Effective tax rate {'increased' if change > 0 else 'decreased'} "
                    f"from {tax_rates[prev]['effective_rate']*100:.1f}% "
                    f"to {tax_rates[curr]['effective_rate']*100:.1f}% in {curr}"
                ),
            })

    # Income volatility
    if len(monthly) >= 3:
        gross_values = [m["gross"] for m in monthly if m["gross"] > 0]
        if gross_values:
            mean = sum(gross_values) / len(gross_values)
            cv   = (sum((g - mean) ** 2 for g in gross_values) / len(gross_values)) ** 0.5 / mean
            if cv > 0.15:
                anomalies.append({
                    "type": "income_volatility",
                    "severity": "high" if cv > 0.25 else "medium",
                    "details": {"coefficient_of_variation": cv, "mean_gross": mean},
                    "message": f"High income volatility detected: {cv*100:.1f}% variation in monthly gross income",
                })

    # SS wage cap
    for year, data in yearly.items():
        ss_limit = SS_WAGE_LIMITS.get(year)
        ss_wages = data.get("ss_wages", data.get("gross", 0))
        if ss_limit and ss_wages >= ss_limit * 0.95:
            cap_month = _find_ss_cap_month(paystubs, year, ss_limit)
            anomalies.append({
                "type": "ss_cap_hit",
                "severity": "info",
                "year": year,
                "details": {"ss_wages": ss_wages, "ss_limit": ss_limit, "cap_month": cap_month},
                "message": f"Social Security wage cap (${ss_limit:,.0f}) reached in {cap_month or year}",
            })

    # Sporadic stock income
    stock_months = [m for m in monthly if m.get("stock_income", 0) > 0]
    if len(stock_months) >= 2 and len(stock_months) < len(monthly) * 0.8:
        mean_stock = sum(m["stock_income"] for m in stock_months) / len(stock_months)
        anomalies.append({
            "type": "stock_income_pattern",
            "severity": "info",
            "details": {
                "months_with_stock":    len(stock_months),
                "total_months":         len(monthly),
                "average_stock_income": mean_stock,
            },
            "message": (
                f"Stock compensation appears in {len(stock_months)} of {len(monthly)} months, "
                "causing bi-monthly income volatility"
            ),
        })

    # Significant deduction changes
    for i in range(1, len(monthly)):
        prev, curr = monthly[i - 1], monthly[i]
        for dtype in ("pretax_deductions", "aftertax_deductions"):
            pv = prev.get(dtype, 0)
            cv = curr.get(dtype, 0)
            if pv > 0:
                chg = (cv - pv) / pv
                if abs(chg) > 0.20:
                    anomalies.append({
                        "type": "deduction_change",
                        "severity": "medium" if abs(chg) > 0.30 else "low",
                        "month": curr["month"],
                        "details": {
                            "deduction_type": dtype.replace("_", " ").title(),
                            "previous": pv, "current": cv, "change_pct": chg,
                        },
                        "message": (
                            f"{dtype.replace('_', ' ').title()} "
                            f"{'increased' if chg > 0 else 'decreased'} "
                            f"by {abs(chg)*100:.0f}% in {curr['month']}"
                        ),
                    })

    return anomalies


def _find_ss_cap_month(paystubs: list, year: int, limit: float) -> Optional[str]:
    ytd = 0.0
    for p in sorted(
        [p for p in paystubs if str(p.get("pay_date", ""))[:4] == str(year)],
        key=lambda x: x.get("pay_date", ""),
    ):
        ytd += _get_value(p, "gross") or 0
        if ytd >= limit:
            pay_date = p.get("pay_date", "")
            return str(pay_date)[:7] if pay_date else None
    return None


# ── Insights ──────────────────────────────────────────────────────────────────

def generate_insights(trends: dict, anomalies: list, w2s: list) -> list[dict]:
    insights  = []
    yearly    = trends.get("yearly_summary", {})
    tax_rates = trends.get("effective_tax_rates", {})
    growth    = trends.get("income_growth", {})

    if tax_rates:
        latest = max(tax_rates)
        rate   = tax_rates[latest]
        if rate["effective_rate"] > 0.25:
            insights.append({
                "category": "tax_optimization", "priority": "high",
                "title": "High Effective Tax Rate",
                "message": (
                    f"Your effective tax rate is {rate['effective_rate']*100:.1f}%. "
                    "Consider maximizing pre-tax deductions (401k, HSA) to reduce taxable income."
                ),
                "data": rate,
            })

    if growth:
        latest = max(growth)
        g = growth[latest]
        if g["gross_growth"] > 0.10:
            insights.append({
                "category": "income_stability", "priority": "info",
                "title": "Strong Income Growth",
                "message": f"Gross income grew by {g['gross_growth']*100:.1f}% (${g['gross_change']:,.0f}) in {latest}.",
                "data": g,
            })
        elif g["gross_growth"] < -0.05:
            insights.append({
                "category": "income_stability", "priority": "medium",
                "title": "Income Decrease",
                "message": f"Gross income decreased by {abs(g['gross_growth'])*100:.1f}% in {latest}. Review if expected.",
                "data": g,
            })

    for anomaly in anomalies:
        if anomaly["type"] == "tax_rate_change" and anomaly["severity"] == "high":
            insights.append({
                "category": "tax_optimization", "priority": "high",
                "title": "Significant Tax Rate Change",
                "message": anomaly["message"], "data": anomaly["details"],
            })
        elif anomaly["type"] == "income_volatility":
            insights.append({
                "category": "income_stability", "priority": "medium",
                "title": "Income Volatility Detected",
                "message": anomaly["message"] + " This may be due to stock compensation or variable bonuses.",
                "data": anomaly["details"],
            })
        elif anomaly["type"] == "ss_cap_hit":
            insights.append({
                "category": "tax_optimization", "priority": "info",
                "title": "SS Wage Cap Reached",
                "message": anomaly["message"] + " Your take-home pay increases after this point.",
                "data": anomaly["details"],
            })

    for w2 in w2s:
        year       = w2.get("year")
        box12_401k = w2.get("box12_401k_pretax", 0) or 0
        box12_roth = w2.get("box12_roth_401k", 0) or 0
        total_401k = box12_401k + box12_roth
        limit_401k = 23000
        if 0 < total_401k < limit_401k * 0.90:
            insights.append({
                "category": "retirement", "priority": "medium",
                "title": f"401(k) Contribution Opportunity ({year})",
                "message": (
                    f"You contributed ${total_401k:,.0f} to 401(k) in {year}. "
                    f"Consider increasing to the ${limit_401k:,} limit to reduce taxable income."
                ),
                "data": {"pretax_401k": box12_401k, "roth_401k": box12_roth,
                         "total": total_401k, "limit": limit_401k},
            })
        box12_hsa = w2.get("box12_hsa", 0) or 0
        hsa_limit = 4150
        if 0 < box12_hsa < hsa_limit * 0.90:
            insights.append({
                "category": "tax_optimization", "priority": "low",
                "title": f"HSA Contribution Opportunity ({year})",
                "message": (
                    f"You contributed ${box12_hsa:,.0f} to HSA in {year}. "
                    f"Consider maximizing to ${hsa_limit:,} limit for triple tax advantage."
                ),
                "data": {"current": box12_hsa, "limit": hsa_limit},
            })

    return insights


# ── Actions ───────────────────────────────────────────────────────────────────

def propose_actions(insights: list, anomalies: list, trends: dict) -> list[dict]:
    actions = []

    for insight in insights:
        data = insight.get("data", {})
        if insight["category"] == "retirement" and "401(k)" in insight["title"]:
            gap = data.get("limit", 0) - data.get("total", 0)
            if gap > 0:
                actions.append({
                    "type": "increase_contribution", "priority": "high",
                    "title": "Increase 401(k) Contribution",
                    "description": (
                        f"Increase 401(k) contribution by ${gap:,.0f}/year "
                        f"(${gap/24:,.0f}/paycheck bi-weekly) to maximize tax savings."
                    ),
                    "impact": f"Potential tax savings: ${gap * 0.24:,.0f} (assuming 24% marginal rate)",
                })
        if insight["category"] == "tax_optimization" and "HSA" in insight["title"]:
            gap = data.get("limit", 0) - data.get("current", 0)
            if gap > 0:
                actions.append({
                    "type": "increase_contribution", "priority": "medium",
                    "title": "Increase HSA Contribution",
                    "description": f"Increase HSA contribution by ${gap:,.0f}/year to maximize triple tax advantage.",
                    "impact": "Pre-tax, grows tax-free, withdrawals for medical expenses are tax-free.",
                })
        if insight["category"] == "tax_optimization" and "High Effective Tax Rate" in insight["title"]:
            actions.append({
                "type": "review_withholding", "priority": "medium",
                "title": "Review Tax Withholding",
                "description": "Your effective tax rate is high. Review W-4 withholding or consult a tax professional.",
                "impact": "Proper withholding prevents large tax bills or refunds at year end.",
            })

    for anomaly in anomalies:
        if anomaly["type"] == "deduction_change" and anomaly["severity"] in ("medium", "high"):
            actions.append({
                "type": "verify_data", "priority": "low",
                "title": f"Verify Deduction Change in {anomaly.get('month', 'recent month')}",
                "description": anomaly["message"] + " Verify this change is expected.",
                "impact": "Catches potential payroll errors.",
            })

    yearly = trends.get("yearly_summary", {})
    if yearly and yearly[max(yearly)]["gross"] > 200000:
        actions.append({
            "type": "consult_professional", "priority": "medium",
            "title": "Consider Tax Planning Consultation",
            "description": (
                "With annual income over $200k, a tax professional can help optimize "
                "backdoor Roth, ESPP timing, and stock option planning."
            ),
            "impact": "Professional advice can identify thousands in tax savings.",
        })

    return actions


# ── Report ────────────────────────────────────────────────────────────────────

def compile_report(summary: dict, trends: dict, anomalies: list,
                   insights: list, actions: list) -> str:
    lines = ["# 📊 Income Intelligence Analysis\n"]

    lines += [
        "## 📁 Data Summary\n",
        f"- **Paystubs analyzed:** {summary.get('paystub_count', 0)}",
        f"- **W-2s analyzed:** {summary.get('w2_count', 0)}",
        f"- **Years covered:** {', '.join(map(str, summary.get('years_covered', [])))}",
        f"- **Employers:** {', '.join(summary.get('employers', []))}",
        "",
    ]

    yearly    = trends.get("yearly_summary", {})
    tax_rates = trends.get("effective_tax_rates", {})
    if yearly:
        lines.append("## 💰 Key Metrics by Year\n")
        for year in sorted(yearly, reverse=True):
            data = yearly[year]
            rate = tax_rates.get(year, {})
            lines += [
                f"### {year}",
                f"- Gross Income: **${data.get('gross', 0):,.0f}**",
                *(
                    [f"- Effective Tax Rate: **{rate.get('effective_rate', 0)*100:.1f}%**"]
                    if rate else []
                ),
                f"- Federal Tax: ${data.get('federal_tax', 0):,.0f}",
                f"- State Tax: ${data.get('state_tax', 0):,.0f}",
                f"- Source: {data.get('source', 'unknown')}",
                "",
            ]

    if anomalies:
        lines.append("## 🔍 Findings\n")
        emoji = {"high": "🔴", "medium": "🟡", "low": "🟢", "info": "ℹ️"}
        for a in anomalies:
            e = emoji.get(a.get("severity", "info"), "•")
            lines.append(f"{e} **{a.get('type','').replace('_',' ').title()}**: {a.get('message','')}")
        lines.append("")

    if insights:
        lines.append("## 💡 Insights\n")
        pemoji = {"high": "⭐", "medium": "📌", "low": "📎", "info": "ℹ️"}
        for ins in insights:
            e = pemoji.get(ins.get("priority", "info"), "•")
            lines += [f"{e} **{ins.get('title','')}**", f"   {ins.get('message','')}", ""]

    if actions:
        lines.append("## ✅ Recommended Actions\n")
        for i, act in enumerate(actions, 1):
            lines += [
                f"### {i}. {act.get('title','')}",
                act.get("description", ""),
                *(
                    [f"\n**Impact:** {act.get('impact')}"]
                    if act.get("impact") else []
                ),
                "",
            ]

    if not yearly and not anomalies and not insights:
        lines += [
            "## ℹ️ No Data Found\n",
            "No income data was found. Please upload paystubs or W-2 documents first.",
        ]

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Entry point with result cache
# ═══════════════════════════════════════════════════════════════════════════════

_cache: dict[tuple, dict] = {}


def _cache_key(person: str) -> tuple:
    """Build a cache key from person name + modification times of all parsed files."""
    pdir = parsed_dir(person)
    mtimes: list[float] = []
    for subdir in ("paystub", "w2"):
        d = pdir / subdir
        if d.exists():
            for f in sorted(d.glob("*.json")):
                mtimes.append(f.stat().st_mtime)
    return (person, tuple(mtimes))


def run_income_analysis(person: str = "Huimin") -> dict:
    """Run the income analysis pipeline and return the full result dict.

    Results are cached by (person, file-mtimes). A re-upload invalidates
    the cache automatically because file mtimes change.
    """
    key = _cache_key(person)
    if key in _cache:
        return {**_cache[key], "trace": _cache[key]["trace"] + ["cache:hit"]}

    trace: list[str] = []
    try:
        data      = load_income_data(person)
        trace.append(f"load_data:ok:{len(data['paystubs'])} paystubs, {len(data['w2s'])} w2s")

        trends    = compute_trends(data["paystubs"], data["w2s"])
        trace.append("compute_trends:ok")

        anomalies = detect_anomalies(trends, data["paystubs"], data["w2s"])
        trace.append(f"detect_anomalies:ok:{len(anomalies)} found")

        insights  = generate_insights(trends, anomalies, data["w2s"])
        trace.append(f"generate_insights:ok:{len(insights)} insights")

        actions   = propose_actions(insights, anomalies, trends)
        trace.append(f"propose_actions:ok:{len(actions)} actions")

        report    = compile_report(data["summary"], trends, anomalies, insights, actions)
        trace.append("compile_report:ok")

        result = {
            "report":       report,
            "insights":     insights,
            "actions":      actions,
            "anomalies":    anomalies,
            "trends":       trends,
            "data_summary": data["summary"],
            "trace":        trace,
            "error":        None,
        }
        _cache[key] = result
        return result

    except Exception as e:
        trace.append(f"error:{e}")
        return {
            "report":       f"❌ Analysis failed: {e}",
            "insights":     [],
            "actions":      [],
            "anomalies":    [],
            "trends":       {},
            "data_summary": {},
            "trace":        trace,
            "error":        str(e),
        }
