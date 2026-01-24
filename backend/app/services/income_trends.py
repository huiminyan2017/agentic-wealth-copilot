"""Service for calculating income trends from paystubs and W2s."""
from __future__ import annotations

import json
from pathlib import Path
from datetime import date, datetime
from collections import defaultdict
from typing import Optional

from backend.app.services.paths import parsed_dir


def _load_paystubs(person: str) -> list[dict]:
    """Load all paystub records for a person."""
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


def _load_w2s(person: str) -> list[dict]:
    """Load all W2 records for a person."""
    pdir = parsed_dir(person) / "w2"
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
    """Parse date from various formats."""
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


def _f(x) -> Optional[float]:
    """Safely convert to float."""
    try:
        return float(x) if x is not None else None
    except Exception:
        return None


def _get_nested_value(data: dict, key: str, subkey: str = "value") -> Optional[float]:
    """
    Get value from nested structure like {"gross": {"value": 100, "details": {...}}}.
    Supports both new schema (nested) and old schema (flat).
    """
    val = data.get(key)
    if val is None:
        return None
    if isinstance(val, dict):
        return _f(val.get(subkey))
    return _f(val)


def _get_nested_details(data: dict, key: str) -> dict:
    """
    Get details dict from nested structure.
    Returns empty dict if not found.
    """
    val = data.get(key)
    if val is None:
        return {}
    if isinstance(val, dict):
        return val.get("details", {})
    return {}


def calculate_income_trends(person: str) -> dict:
    """
    Calculate monthly income trends and W2 annual summaries.
    
    Returns:
        Dictionary with:
        - person: str
        - months: list of month keys
        - series: list of monthly data points
        - paystubs: list of individual paystub records (for drill-down)
        - insights: list of insight strings
        - w2_annual_summaries: list of W2 annual summaries
    """
    records = _load_paystubs(person)
    w2_records = _load_w2s(person)

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
        "stock_pay": 0.0,
        "missing_core_fields": 0,
        "gross_details": defaultdict(float),  # Track gross breakdown by component
    })

    # core fields we care about for "data quality"
    core_fields = ["gross", "net_pay", "taxes"]
    
    # Store individual paystubs for drill-down
    paystubs = []

    # Aggregate paystub data by month
    for r in records:
        pd = _parse_date(r.get("pay_date"))
        if pd is None:
            continue
        month_key = f"{pd.year:04d}-{pd.month:02d}"

        # Extract values from new nested schema
        gross = _get_nested_value(r, "gross")
        net = _get_nested_value(r, "net_pay")
        pretax = _get_nested_value(r, "pretax_deductions")
        aftertax = _get_nested_value(r, "aftertax_deductions")
        taxes_val = _get_nested_value(r, "taxes")
        stock = _get_nested_value(r, "stock_pay")
        # Get validation as full dict (not just value) for detailed checks
        validation = r.get("validation")
        
        # Get tax details
        taxes_details = _get_nested_details(r, "taxes")
        fed = _f(taxes_details.get("federal"))
        st = _f(taxes_details.get("state"))
        ss = _f(taxes_details.get("ss"))
        med = _f(taxes_details.get("medicare"))
        
        # Get gross details
        gross_details = _get_nested_details(r, "gross")
        
        # Get deduction details
        pretax_details = _get_nested_details(r, "pretax_deductions")
        aftertax_details = _get_nested_details(r, "aftertax_deductions")
        
        # Get stock details
        stock_details = _get_nested_details(r, "stock_pay")

        m = monthly[month_key]
        m["paychecks"] += 1

        if gross is not None: m["gross"] += gross
        if net is not None: m["net"] += net
        if fed is not None: m["federal_tax"] += abs(fed)  # taxes stored as negative
        if st is not None: m["state_tax"] += abs(st)
        if ss is not None: m["ss_tax"] += abs(ss)
        if med is not None: m["medicare_tax"] += abs(med)
        if pretax is not None: m["pre_tax_deductions"] += abs(pretax)
        if aftertax is not None: m["post_tax_deductions"] += abs(aftertax)
        if stock is not None: m["stock_pay"] += stock
        
        # Aggregate gross details by component
        for key, val in gross_details.items():
            if val is not None:
                m["gross_details"][key] += val

        # missing counter
        missing = 0
        for f in core_fields:
            if _get_nested_value(r, f) is None:
                missing += 1
        if missing:
            m["missing_core_fields"] += missing
        
        # Store individual paystub for drill-down
        paystubs.append({
            "pay_date": r.get("pay_date"),
            "employer_name": r.get("employer_name"),
            "month": month_key,
            "gross": {
                "value": gross,
                "details": gross_details
            },
            "pretax_deductions": {
                "value": pretax,
                "details": pretax_details
            },
            "taxes": {
                "value": taxes_val,
                "details": taxes_details
            },
            "aftertax_deductions": {
                "value": aftertax,
                "details": aftertax_details
            },
            "net_pay": net,
            "stock_pay": {
                "value": stock,
                "details": stock_details
            },
            "validation": validation,
            "parser": r.get("parser"),
        })

    # sort months
    months = sorted(monthly.keys())

    series = []
    insights = []

    # Build monthly series and generate insights
    prev_gross = None
    prev_gross_details = None
    for mk in months:
        m = monthly[mk]
        total_tax = m["federal_tax"] + m["state_tax"] + m["ss_tax"] + m["medicare_tax"]
        eff_tax_rate = (total_tax / m["gross"]) if m["gross"] > 1e-9 else None
        savings_like = ((m["gross"] - total_tax - m["net"]) if (m["gross"] > 0 and m["net"] > 0) else None)
        
        # Calculate month-over-month change and reason
        mom_change = None
        mom_reason = None
        if prev_gross is not None and prev_gross_details is not None and m["gross"] > 0 and prev_gross > 0:
            mom_change = round((m["gross"] - prev_gross) / prev_gross * 100, 1)
            # Build reason from component differences
            curr_details = dict(m["gross_details"])
            diff_components = []
            all_keys = set(curr_details.keys()) | set(prev_gross_details.keys())
            for key in all_keys:
                curr_val = curr_details.get(key, 0) or 0
                prev_val = prev_gross_details.get(key, 0) or 0
                diff = curr_val - prev_val
                if abs(diff) > 100:
                    diff_components.append((key, diff))
            diff_components.sort(key=lambda x: abs(x[1]), reverse=True)
            if diff_components:
                reasons = []
                for key, diff in diff_components[:3]:
                    name = key.replace("_", " ").title()
                    if diff > 0:
                        reasons.append(f"{name}: +${diff:,.0f}")
                    else:
                        reasons.append(f"{name}: ${diff:,.0f}")
                mom_reason = ", ".join(reasons)
        
        # Convert gross_details to regular dict with rounded values
        gross_details_rounded = {k: round(v, 2) for k, v in m["gross_details"].items()}

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
            "stock_pay": round(m["stock_pay"], 2),
            "missing_core_fields": m["missing_core_fields"],
            "implied_other_outflows": round(savings_like, 2) if savings_like is not None else None,
            "gross_details": gross_details_rounded,
            "mom_change_pct": mom_change,
            "mom_reason": mom_reason,
        })

        # simple insight: large jump/drop in monthly gross
        if prev_gross is not None and prev_gross_details is not None and m["gross"] > 0 and prev_gross > 0:
            change = (m["gross"] - prev_gross) / prev_gross
            if abs(change) >= 0.25:
                # Analyze which gross components changed significantly
                curr_details = dict(m["gross_details"])
                diff_components = []
                
                # Calculate difference for each component
                all_keys = set(curr_details.keys()) | set(prev_gross_details.keys())
                for key in all_keys:
                    curr_val = curr_details.get(key, 0) or 0
                    prev_val = prev_gross_details.get(key, 0) or 0
                    diff = curr_val - prev_val
                    if abs(diff) > 100:  # Only report significant differences (>$100)
                        diff_components.append((key, diff))
                
                # Sort by absolute difference
                diff_components.sort(key=lambda x: abs(x[1]), reverse=True)
                
                # Build explanation from top contributors
                if diff_components:
                    explanations = []
                    for key, diff in diff_components[:3]:  # Top 3 contributors
                        name = key.replace("_", " ").title()
                        if diff > 0:
                            explanations.append(f"{name} +${diff:,.0f}")
                        else:
                            explanations.append(f"{name} ${diff:,.0f}")
                    reason = ", ".join(explanations)
                else:
                    reason = "details unavailable"
                
                if change >= 0.25:
                    insights.append(f"{mk}: Gross income increased by {change*100:.1f}% vs previous month ({reason})")
                else:
                    insights.append(f"{mk}: Gross income decreased by {abs(change)*100:.1f}% vs previous month ({reason})")
        
        if m["missing_core_fields"] > 0:
            insights.append(f"{mk}: Some paystubs have missing fields (total missing core fields this month: {m['missing_core_fields']}).")

        prev_gross = m["gross"] if m["gross"] > 0 else prev_gross
        prev_gross_details = dict(m["gross_details"]) if m["gross"] > 0 else prev_gross_details

    # Add W2 annual summaries
    w2_summaries = []
    for w2 in w2_records:
        year = w2.get("year")
        if year:
            w2_summaries.append({
                "year": year,
                "wages": _f(w2.get("wages")),
                "federal_tax_withheld": _f(w2.get("federal_tax_withheld")),
                "state_tax_withheld": _f(w2.get("state_tax_withheld")),
                "ss_tax_withheld": _f(w2.get("ss_tax_withheld")),
                "medicare_tax_withheld": _f(w2.get("medicare_tax_withheld")),
                "ss_wages": _f(w2.get("ss_wages")),
                "medicare_wages": _f(w2.get("medicare_wages")),
                "state_wages": _f(w2.get("state_wages")),
                # Box 12 codes with meaningful names
                "box12_401k_pretax": _f(w2.get("box12_401k_pretax")),
                "box12_hsa": _f(w2.get("box12_hsa")),
                "box12_roth_401k": _f(w2.get("box12_roth_401k")),
                "box12_gtl": _f(w2.get("box12_gtl")),
                "missing_fields": w2.get("missing_fields", []),
            })
    
    # Add validation summary to insights (support both old single value and new dict format)
    def has_validation_issues(p):
        v = p.get("validation")
        if v is None:
            return False
        if isinstance(v, dict):
            # New format: check all diff fields
            for key in ["net_pay_diff", "tax_sum_diff", "pretax_sum_diff", "aftertax_sum_diff"]:
                val = v.get(key)
                if val is not None and abs(val) > 0.02:
                    return True
            return False
        else:
            # Old format: single value
            return abs(v) > 0.02
    
    invalid_paystubs = [p for p in paystubs if has_validation_issues(p)]
    if invalid_paystubs:
        insights.insert(0, f"⚠️ {len(invalid_paystubs)} paystub(s) have validation issues")
    else:
        insights.insert(0, f"✓ All {len(paystubs)} paystubs passed validation")
    
    # Compare W2 totals with paystub YTD for validation insights
    for w2_sum in w2_summaries:
        year = w2_sum["year"]
        # Find December paystub for that year to compare YTD
        dec_key = f"{year}-12"
        if dec_key in monthly:
            m_dec = monthly[dec_key]
            # Check if paystub totals roughly match W2 (allow 5% variance)
            if w2_sum["wages"] and m_dec["gross"] > 0:
                diff_pct = abs(w2_sum["wages"] - m_dec["gross"]) / w2_sum["wages"]
                if diff_pct > 0.05:
                    insights.append(f"{year} W2: Wages ${w2_sum['wages']:,.2f} differ from Dec YTD by {diff_pct*100:.1f}% - verify paystub completeness")

    return {
        "person": person,
        "months": months,
        "series": series,
        "paystubs": paystubs,  # Individual paystubs for drill-down
        "insights": insights[:20],
        "w2_annual_summaries": sorted(w2_summaries, key=lambda x: x["year"]),
    }
