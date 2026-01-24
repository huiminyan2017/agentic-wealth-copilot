"""Wealth & Planning page.

This page allows users to track their current wealth (cash, property, stocks, 401K)
and set financial targets for retirement planning.
"""

import streamlit as st
import json
from pathlib import Path
from datetime import date

st.title("💰 Wealth & Planning")

# ---- Data Storage ----
# Use resolve() to get absolute path from the file location
_THIS_FILE = Path(__file__).resolve()
DATA_DIR = _THIS_FILE.parent.parent.parent / "data" / "parsed"
DATA_RAW_DIR = _THIS_FILE.parent.parent.parent / "data" / "raw"

def get_wealth_file(person: str) -> Path:
    """Get the wealth data file path for a specific person."""
    return DATA_DIR / person / "wealth.json"

def load_wealth_data(person: str):
    """Load wealth data from JSON file for a specific person."""
    wealth_file = get_wealth_file(person)
    if wealth_file.exists():
        with open(wealth_file, "r") as f:
            return json.load(f)
    return {
        "current": {
            "cash": 0.0,
            "primary_property_total": 0.0,
            "primary_owners": 1,
            "primary_property": 0.0,
            "investment_properties_total": 0.0,
            "investment_owners": 1,
            "investment_properties": 0.0,
            "stock_value": 0.0,
            "retirement_401k": 0.0,
        },
        "targets": {
            "target_401k": 0.0,
            "target_non_retirement": 0.0,
        },
        "last_updated": None,
    }

def save_wealth_data(data, person: str):
    """Save wealth data to JSON file for a specific person."""
    person_dir = DATA_DIR / person
    person_dir.mkdir(parents=True, exist_ok=True)
    data["last_updated"] = date.today().isoformat()
    wealth_file = get_wealth_file(person)
    with open(wealth_file, "w") as f:
        json.dump(data, f, indent=2)

# ---- Dynamic Person Selection ----
def get_available_people():
    """Get list of people from data/raw and data/parsed directories."""
    people = set()
    if DATA_RAW_DIR.exists():
        for item in DATA_RAW_DIR.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                people.add(item.name)
    # Also check for existing wealth files in person folders
    if DATA_DIR.exists():
        for item in DATA_DIR.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                wealth_file = item / "wealth.json"
                if wealth_file.exists():
                    people.add(item.name)
    return sorted(people) if people else ["Person1"]

available_people = get_available_people()
person = st.selectbox("👤 Select Person", available_people, key="wealth_person")

# Load existing data for selected person
wealth_data = load_wealth_data(person)

# ---- Current Wealth Section ----
st.header("📊 Current Wealth")

col1, col2 = st.columns(2)

with col1:
    cash = st.number_input(
        "💵 Cash & Savings",
        min_value=0.0,
        value=float(wealth_data["current"].get("cash", 0)),
        step=1000.0,
        format="%.2f",
        help="Total cash in bank accounts, savings, money market funds"
    )
    
    # Primary Property with ownership split
    st.markdown("**🏠 Primary Property**")
    prop_cols = st.columns([3, 1])
    with prop_cols[0]:
        primary_property_total = st.number_input(
            "Total Value",
            min_value=0.0,
            value=float(wealth_data["current"].get("primary_property_total", wealth_data["current"].get("primary_property", 0))),
            step=10000.0,
            format="%.2f",
            key=f"primary_total_{person}",
            help="Total property value (before dividing by owners)"
        )
    with prop_cols[1]:
        primary_owners = st.number_input(
            "Owners",
            min_value=1,
            value=int(wealth_data["current"].get("primary_owners", 1)),
            step=1,
            key=f"primary_owners_{person}",
            help="Number of people sharing ownership"
        )
    primary_property = primary_property_total / primary_owners
    if primary_owners > 1:
        st.caption(f"Your share: **${primary_property:,.0f}**")
    
    # Investment Properties with ownership split
    st.markdown("**🏘️ Investment Properties**")
    inv_cols = st.columns([3, 1])
    with inv_cols[0]:
        investment_properties_total = st.number_input(
            "Total Value",
            min_value=0.0,
            value=float(wealth_data["current"].get("investment_properties_total", wealth_data["current"].get("investment_properties", 0))),
            step=10000.0,
            format="%.2f",
            key=f"inv_total_{person}",
            help="Total investment property value (before dividing by owners)"
        )
    with inv_cols[1]:
        investment_owners = st.number_input(
            "Owners",
            min_value=1,
            value=int(wealth_data["current"].get("investment_owners", 1)),
            step=1,
            key=f"inv_owners_{person}",
            help="Number of people sharing ownership"
        )
    investment_properties = investment_properties_total / investment_owners
    if investment_owners > 1:
        st.caption(f"Your share: **${investment_properties:,.0f}**")

with col2:
    stock_value = st.number_input(
        "📈 Stock & Investment Value",
        min_value=0.0,
        value=float(wealth_data["current"].get("stock_value", 0)),
        step=1000.0,
        format="%.2f",
        help="Value of stocks, ETFs, mutual funds in taxable brokerage accounts"
    )
    
    retirement_401k = st.number_input(
        "🏦 401(k) / Retirement Accounts",
        min_value=0.0,
        value=float(wealth_data["current"].get("retirement_401k", 0)),
        step=1000.0,
        format="%.2f",
        help="Total value of 401(k), IRA, Roth IRA, and other retirement accounts"
    )

# Calculate totals (using YOUR share of properties)
total_wealth = cash + primary_property + investment_properties + stock_value + retirement_401k
# Non-retirement investable wealth excludes primary property AND 401(k) 
# (401k has its own target, so we track it separately)
non_retirement_wealth = cash + investment_properties + stock_value

def format_money(amount):
    """Format large numbers in readable format (e.g., $1.2M, $350K)."""
    if amount >= 1_000_000:
        return f"${amount/1_000_000:.1f}M"
    elif amount >= 1_000:
        return f"${amount/1_000:.0f}K"
    else:
        return f"${amount:,.0f}"

st.divider()

# Display current wealth summary
st.subheader("Current Wealth Summary")

# Use 3 columns per row for better readability
row1_cols = st.columns(3)
with row1_cols[0]:
    st.metric("💵 Cash", format_money(cash))
with row1_cols[1]:
    st.metric("🏠 Primary Home", format_money(primary_property))
with row1_cols[2]:
    st.metric("🏘️ Investment Props", format_money(investment_properties))

row2_cols = st.columns(3)
with row2_cols[0]:
    st.metric("📈 Stocks", format_money(stock_value))
with row2_cols[1]:
    st.metric("🏦 401(k)", format_money(retirement_401k))
with row2_cols[2]:
    st.metric("**💰 Total**", format_money(total_wealth))

# Show non-retirement wealth separately
st.info(f"💡 **Non-Retirement Wealth: {format_money(non_retirement_wealth)}** (Cash + Investment Props + Stocks, excludes primary home & 401k)")

st.divider()

# ---- Targets Section ----
st.header("🎯 Financial Targets")

st.caption("⚠️ **Note:** 401(k) and non-retirement wealth are tracked separately. Primary property is excluded because it's for living, not generating returns.")

target_col1, target_col2 = st.columns(2)

with target_col1:
    target_401k = st.number_input(
        "🎯 Target 401(k) Balance",
        min_value=0.0,
        value=float(wealth_data["targets"].get("target_401k", 0)),
        step=10000.0,
        format="%.2f",
        help="Your goal for retirement account balance"
    )

with target_col2:
    target_non_retirement = st.number_input(
        "🎯 Target Non-Retirement Wealth",
        min_value=0.0,
        value=float(wealth_data["targets"].get("target_non_retirement", wealth_data["targets"].get("target_investable_wealth", 0))),
        step=50000.0,
        format="%.2f",
        help="Your non-retirement wealth goal (cash + investment properties + stocks, excluding 401k and primary home)"
    )

# Progress towards goals
st.divider()
st.subheader("Progress Towards Goals")

prog_col1, prog_col2 = st.columns(2)

with prog_col1:
    if target_401k > 0:
        progress_401k = min(retirement_401k / target_401k, 1.0)
        st.metric(
            "401(k) Progress",
            f"{progress_401k * 100:.1f}%",
            delta=f"${target_401k - retirement_401k:,.0f} to go" if retirement_401k < target_401k else "Goal reached! 🎉"
        )
        st.progress(progress_401k)
    else:
        st.info("Set a 401(k) target to track progress")

with prog_col2:
    if target_non_retirement > 0:
        progress_wealth = min(non_retirement_wealth / target_non_retirement, 1.0)
        st.metric(
            "Non-Retirement Wealth Progress",
            f"{progress_wealth * 100:.1f}%",
            delta=f"${target_non_retirement - non_retirement_wealth:,.0f} to go" if non_retirement_wealth < target_non_retirement else "Goal reached! 🎉"
        )
        st.progress(progress_wealth)
    else:
        st.info("Set a non-retirement wealth target to track progress")

st.divider()

# Save button
if st.button("💾 Save Wealth Data", type="primary"):
    wealth_data["current"] = {
        "cash": cash,
        "primary_property_total": primary_property_total,
        "primary_owners": primary_owners,
        "primary_property": primary_property,  # Your share
        "investment_properties_total": investment_properties_total,
        "investment_owners": investment_owners,
        "investment_properties": investment_properties,  # Your share
        "stock_value": stock_value,
        "retirement_401k": retirement_401k,
    }
    wealth_data["targets"] = {
        "target_401k": target_401k,
        "target_non_retirement": target_non_retirement,
    }
    save_wealth_data(wealth_data, person)
    st.success(f"✅ Wealth data saved for {person}!")

# Show last updated
if wealth_data.get("last_updated"):
    st.caption(f"Last updated: {wealth_data['last_updated']}")
