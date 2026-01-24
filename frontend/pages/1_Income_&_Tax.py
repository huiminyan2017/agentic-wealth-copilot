"""Income & Tax page.

This page will guide users through uploading W‑2 forms and paystubs,
present extracted information, visualise income trends and explain
tax concepts using personalised examples.  Currently it presents a
placeholder message.
"""

import streamlit as st
import pandas as pd
import re
import os
from pathlib import Path
import plotly.graph_objects as go
from api import request_json
from state import ensure_session

ensure_session()

st.title("Income & Tax")

# ---- Dynamic Person Selection ----
DATA_RAW_DIR = Path(__file__).parent.parent.parent / "data" / "raw"

def get_existing_people() -> list[str]:
    """Get list of people from data/raw directory, excluding hidden/test folders."""
    if not DATA_RAW_DIR.exists():
        return []
    people = []
    for item in DATA_RAW_DIR.iterdir():
        if item.is_dir() and not item.name.startswith('.'):
            people.append(item.name)
    return sorted(people)

def create_person_folder(name: str) -> bool:
    """Create folder structure for a new person."""
    person_dir = DATA_RAW_DIR / name
    try:
        (person_dir / "paystub").mkdir(parents=True, exist_ok=True)
        (person_dir / "w2").mkdir(parents=True, exist_ok=True)
        return True
    except Exception:
        return False

# Get existing people and add "Add New" option
existing_people = get_existing_people()
person_options = existing_people + ["➕ Add New Person"]

selected_option = st.selectbox(
    "Person", 
    person_options, 
    index=st.session_state.selected_person_index
)

# Handle "Add New Person" selection
if selected_option == "➕ Add New Person":
    new_person_name = st.text_input(
        "Enter new person's name:",
        placeholder="e.g., John",
        help="Name will be used as folder name (no spaces recommended)"
    )
    
    if new_person_name:
        # Validate name (alphanumeric and basic chars only)
        if re.match(r'^[A-Za-z][A-Za-z0-9_-]*$', new_person_name):
            if new_person_name in existing_people:
                st.warning(f"'{new_person_name}' already exists. Select from dropdown.")
            elif st.button(f"✅ Create '{new_person_name}'", type="primary"):
                if create_person_folder(new_person_name):
                    st.success(f"Created folder for '{new_person_name}'!")
                    # Update selection to the new person
                    st.session_state.selected_person_index = len(existing_people)  # Will be updated on rerun
                    st.rerun()
                else:
                    st.error("Failed to create folder. Check permissions.")
        else:
            st.error("Name must start with a letter and contain only letters, numbers, underscores, or hyphens.")
    
    st.info("👆 Enter a name above to create a new person's data folder.")
    st.stop()  # Don't show rest of page until person is created

person = selected_option

# ---- Quick Actions ----
col_load, col_analyze = st.columns(2)

with col_load:
    if st.button("📈 Load Trends Now", type="primary", use_container_width=True):
        try:
            trends = request_json("GET", f"/api/income/trends?person={person}")
            st.session_state["income_trends"] = trends
            
            # Check if data was found
            if not trends.get("has_data", True):
                st.warning(f"📭 No income documents found for '{person}'.")
                st.info("💡 **To get started:** Expand the **'📁 Document Ingestion (Scan & Ingest Files)'** section below, then:\n\n1. Click **'🔍 Scan raw folders'** to find paystubs/W-2s\n2. Click **'📥 Ingest All'** to process them\n3. Come back here and click **'📈 Load Trends Now'** again")
            else:
                st.success("✅ Trends loaded!")
                st.rerun()
        except Exception as e:
            st.error(f"Failed to load trends: {e}")

with col_analyze:
    if st.button("🤖 Analyze My Income & Taxes", type="secondary", use_container_width=True):
        with st.spinner("🔍 Running Income Intelligence Agent..."):
            try:
                result = request_json("POST", "/api/income/analyze", {"person": person})
                st.session_state["income_analysis"] = result
                
                if result.get("error"):
                    st.error(f"Analysis failed: {result['error']}")
                else:
                    st.success("✅ Analysis complete!")
                    st.rerun()
            except Exception as e:
                st.error(f"Failed to analyze: {e}")

# Display analysis results if available
if st.session_state.get("income_analysis"):
    analysis = st.session_state["income_analysis"]
    
    if not analysis.get("error"):
        with st.expander("📊 Income Intelligence Analysis", expanded=True):
            # Show the main report
            st.markdown(analysis.get("report", "No report generated."))
            
            # Show execution trace in a collapsible section
            if analysis.get("trace"):
                with st.expander("🔧 Debug: Execution Trace", expanded=False):
                    for t in analysis["trace"]:
                        st.text(t)

st.divider()

# Make the ingestion section collapsible
with st.expander("📁 Document Ingestion (Scan & Ingest Files)", expanded=False):
    st.subheader("Batch scan raw folders")
    st.caption("Looks in: data/raw/<person>/w2 and data/raw/<person>/paystub. Preview first, then you confirm ingestion.")

    # ---- Session state ----
    if "scan_items" not in st.session_state:
        st.session_state.scan_items = []

    if "selected_files" not in st.session_state:
        st.session_state.selected_files = set()

    if "last_ingest_result" not in st.session_state:
        st.session_state.last_ingest_result = None

    if "pending_select_all" not in st.session_state:
        st.session_state.pending_select_all = False

    if "pending_clear" not in st.session_state:
        st.session_state.pending_clear = False


    def infer_year_from_path(path: str):
        m = re.search(r"(20\d{2})", path)
        return m.group(1) if m else "Unknown"


    # ---- Step 1: Scan ----
    if st.button("🔍 Scan raw folders"):
        resp = request_json("GET", f"/api/income/scan?person={person}")
        st.session_state.scan_items = resp["items"]
        st.session_state.selected_files = set()
        st.session_state.last_ingest_result = None
        st.rerun()

    items = st.session_state.scan_items
    has_items = len(items) > 0

    st.divider()

    # ---- Build DataFrame ----
    if items:
        rows = []
        for item in items:
            year = infer_year_from_path(item["rel_path"])
            rows.append({
                "Type": item["kind"],
                "Employer": item["employer"],
                "Year": year,
                "Path": item["rel_path"],
                "SHA": item["sha256"][:10] + "..."
            })

        df = pd.DataFrame(rows)

        # ---- Filters ----
        st.subheader("Filters")

        fcol1, fcol2 = st.columns([1, 1])

        with fcol1:
            type_filter = st.multiselect(
                "File type",
                options=sorted(df["Type"].unique()),
                default=list(df["Type"].unique())
            )

        with fcol2:
            year_filter = st.multiselect(
                "Year",
                options=sorted(df["Year"].unique()),
                default=list(df["Year"].unique())
            )

        filtered_df = df[
            df["Type"].isin(type_filter) &
            df["Year"].isin(year_filter)
        ].reset_index(drop=True)

        visible_paths = set(filtered_df["Path"].tolist())

        # ---- Apply pending selection actions BEFORE rendering ----
        if st.session_state.pending_select_all:
            for p in visible_paths:
                st.session_state.selected_files.add(p)
            st.session_state.pending_select_all = False
            st.rerun()

        if st.session_state.pending_clear:
            st.session_state.selected_files = set()
            st.session_state.pending_clear = False
            st.rerun()

        # ---- Add Select column AFTER applying state ----
        filtered_df.insert(
            0,
            "Select",
            filtered_df["Path"].apply(lambda p: p in st.session_state.selected_files)
        )

        # ---- Preview table ----
        st.subheader("Preview files")

        edited_df = st.data_editor(
            filtered_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Select": st.column_config.CheckboxColumn(required=True)
            },
            disabled=["Type", "Employer", "Year", "Path", "SHA"],
        )

        # ---- Sync selections from table edits ----
        new_selected = set()
        for _, row in edited_df.iterrows():
            if row["Select"]:
                new_selected.add(row["Path"])

        st.session_state.selected_files = new_selected

        st.write(f"Selected: {len(st.session_state.selected_files)} files")

        # ---- Selection tools (now AFTER the table) ----
        st.divider()
        st.subheader("Selection tools")

        col1, col2 = st.columns([1, 1])

        with col1:
            if st.button("✅ Select all (visible)", disabled=not has_items):
                st.session_state.pending_select_all = True
                st.rerun()

        with col2:
            if st.button("❌ Clear selection", disabled=not has_items):
                st.session_state.pending_clear = True
                st.rerun()

        st.divider()

        # ---- Step 3: Ingest ----
        if st.button("📥 Ingest selected", disabled=len(st.session_state.selected_files) == 0):
            with st.spinner("🔄 Parsing and ingesting documents... This may take a moment."):
                payload = {
                    "person": person,
                    "rel_paths": list(st.session_state.selected_files),
                }
                res = request_json("POST", "/api/income/ingest", payload)
                st.session_state.last_ingest_result = res
            st.rerun()

    else:
        st.info("Click **Scan raw folders** to preview files.")

    # ---- Results ----
    res = st.session_state.last_ingest_result
    if res:
        st.success(f'Ingested={res["ingested"]}  Skipped={res["skipped"]}')

        if res.get("skip_reasons"):
            st.subheader("Skipped file reasons")

            for reason, count in res["skip_reasons"].items():
                st.write(f"• {reason.replace('_',' ').title()}: {count}")

        if res.get("skipped_files"):
            with st.expander("View skipped files"):
                st.dataframe(pd.DataFrame(res["skipped_files"]), use_container_width=True)

        if res.get("errors"):
            st.warning("Errors:")
            st.write(res["errors"])
# End of ingestion expander

st.divider()

# Analytics section anchor
st.header("Income trend analytics")

# Show a helpful message if user wants to skip ingestion
if not st.session_state.get("income_trends") and not st.session_state.get("scan_items"):
    st.info("💡 Tip: Click **'Load Trends Now'** at the top to view analytics of already ingested data, or scan/ingest new files first.")

if st.button("📈 Load trends"):
    try:
        trends = request_json("GET", f"/api/income/trends?person={person}")
        st.session_state["income_trends"] = trends
        
        # Check if data was found
        if not trends.get("has_data", True):
            st.warning(f"📭 No income documents found for '{person}'.")
            st.info("💡 **To get started:** Expand the **'📁 Document Ingestion (Scan & Ingest Files)'** section above, then:\n\n1. Click **'🔍 Scan raw folders'** to find paystubs/W-2s\n2. Click **'📥 Ingest All'** to process them\n3. Come back here and click **'📈 Load trends'** again")
        else:
            st.success("✅ Trends loaded!")
    except Exception as e:
        st.error(f"Failed to load trends: {e}")

trends = st.session_state.get("income_trends")
# Only process analytics if we have actual data
if trends and trends.get("has_data", True):
    series = pd.DataFrame(trends["series"])
    paystubs = trends.get("paystubs", [])

    # Display W2 Annual Summaries at the top
    if trends.get("w2_annual_summaries"):
        st.subheader("📄 W2 Annual Summaries")
        w2_df = pd.DataFrame(trends["w2_annual_summaries"])
        
        # Format currency columns
        currency_cols = ["wages", "federal_tax_withheld", "state_tax_withheld", 
                        "ss_tax_withheld", "medicare_tax_withheld", 
                        "ss_wages", "medicare_wages", "state_wages",
                        "box12_401k_pretax", "box12_hsa", "box12_roth_401k", "box12_gtl"]
        
        display_df = w2_df.copy()
        for col in currency_cols:
            if col in display_df.columns:
                display_df[col] = display_df[col].apply(
                    lambda x: f"${x:,.2f}" if pd.notna(x) else "N/A"
                )
        
        # Rename columns for better display
        display_df = display_df.rename(columns={
            "wages": "Wages",
            "federal_tax_withheld": "Federal Tax",
            "state_tax_withheld": "State Tax",
            "ss_tax_withheld": "SS Tax",
            "medicare_tax_withheld": "Medicare Tax",
            "ss_wages": "SS Wages",
            "medicare_wages": "Medicare Wages",
            "state_wages": "State Wages",
            "box12_401k_pretax": "401(k) Pre-tax (D)",
            "box12_hsa": "HSA (W)",
            "box12_roth_401k": "Roth 401(k) (AA)",
            "box12_gtl": "GTL >$50k (C)",
            "year": "Year"
        })
        
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        
        # Show W2 bar chart for comparison
        st.subheader("W2 Annual Wages & Taxes")
        w2_chart_df = w2_df[["year", "wages", "federal_tax_withheld", "state_tax_withheld"]].copy()
        w2_chart_df["year"] = w2_chart_df["year"].astype(str)
        st.bar_chart(w2_chart_df.set_index("year"))
        
        st.divider()
    
    # Display individual paystubs with drill-down
    if paystubs:
        st.header("📊 Individual Paystubs")
        
        # Helper function to format validation status with emoji
        def format_validation_check(diff_val, threshold=0.02):
            """Return emoji status for a single validation check."""
            if diff_val is None:
                return "⬜"  # Not available
            elif abs(diff_val) <= threshold:
                return "✅"  # Pass
            elif abs(diff_val) <= 1.0:
                return "🟡"  # Minor discrepancy
            else:
                return "❌"  # Fail
        
        def get_validation_summary(validation):
            """Build a compact validation summary string from validation dict."""
            if validation is None:
                return "⬜⬜⬜⬜", "No validation data"
            
            if isinstance(validation, dict):
                net = validation.get("net_pay_diff")
                tax = validation.get("tax_sum_diff")
                pretax = validation.get("pretax_sum_diff")
                aftertax = validation.get("aftertax_sum_diff")
            else:
                # Old format: single value
                return format_validation_check(validation) + "⬜⬜⬜", f"Legacy: ${validation:.2f}"
            
            # Build emoji status strip: [Net][Tax][Pre][Post]
            status = (
                format_validation_check(net) +
                format_validation_check(tax) +
                format_validation_check(pretax) +
                format_validation_check(aftertax)
            )
            
            # Build tooltip details
            details = []
            if net is not None: details.append(f"Net: ${net:.2f}")
            if tax is not None: details.append(f"Tax: ${tax:.2f}")
            if pretax is not None: details.append(f"Pre: ${pretax:.2f}")
            if aftertax is not None: details.append(f"Post: ${aftertax:.2f}")
            
            return status, " | ".join(details) if details else "No details"
        
        def count_validation_issues(validation):
            """Count number of validation checks that failed."""
            if validation is None:
                return 0
            if isinstance(validation, dict):
                issues = 0
                for key in ["net_pay_diff", "tax_sum_diff", "pretax_sum_diff", "aftertax_sum_diff"]:
                    val = validation.get(key)
                    if val is not None and abs(val) > 0.02:
                        issues += 1
                return issues
            else:
                return 1 if abs(validation) > 0.02 else 0
        
        # Summary metrics
        total_paystubs = len(paystubs)
        paystubs_with_issues = sum(1 for p in paystubs if count_validation_issues(p.get("validation")) > 0)
        total_checks = sum(4 for p in paystubs if isinstance(p.get("validation"), dict))
        failed_checks = sum(count_validation_issues(p.get("validation")) for p in paystubs)
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Paystubs", total_paystubs)
        with col2:
            st.metric("All Checks Pass", total_paystubs - paystubs_with_issues, delta="✅" if paystubs_with_issues == 0 else None)
        with col3:
            st.metric("Has Issues", paystubs_with_issues, delta="⚠️" if paystubs_with_issues > 0 else None)
        with col4:
            pass_rate = ((total_checks - failed_checks) / total_checks * 100) if total_checks > 0 else 0
            st.metric("Check Pass Rate", f"{pass_rate:.0f}%")
        
        # Legend for validation columns with expandable explanation
        with st.expander("ℹ️ **Validation Checks Explained** — Click to learn what each check means"):
            st.markdown("""
Each paystub goes through **4 validation checks** to ensure the parser extracted values correctly:

---

### 1️⃣ **Net Pay Balance Check** (`Net`)
**Formula:** `Gross Pay − Taxes − Pre-tax Deductions − Post-tax Deductions − Stock Comp ≈ Net Pay`

This is the fundamental paycheck equation. Your gross earnings minus all deductions and taxes should equal your take-home pay. If this fails, it usually means:
- A deduction category was missed during parsing
- Gross pay includes/excludes something unexpected (like imputed income)
- Stock compensation wasn't properly separated

---

### 2️⃣ **Tax Sum Check** (`Tax`)
**Formula:** `Taxes.total − (Federal + State + Social Security + Medicare + Other) ≈ 0`

Verifies that the individual tax line items (federal withholding, state tax, FICA taxes) add up to the total taxes shown on the paystub. A mismatch might indicate:
- Local/city taxes not captured separately
- SDI (State Disability Insurance) categorized differently
- Additional Medicare tax for high earners

---

### 3️⃣ **Pre-tax Deductions Sum Check** (`Pre`)
**Formula:** `Pre-tax.total − (401k + HSA + FSA + Commuter + ...) ≈ 0`

Pre-tax deductions reduce your taxable income. Common items include:
- **401(k)** contributions (traditional)
- **HSA** (Health Savings Account)
- **FSA** (Flexible Spending Account) — medical & dependent care
- **Commuter benefits** (transit, parking)
- **Health/Dental/Vision premiums** (employee portion)

---

### 4️⃣ **Post-tax Deductions Sum Check** (`Post`)
**Formula:** `Post-tax.total − (Roth 401k + ESPP + Life Insurance + ...) ≈ 0`

Post-tax deductions come out after taxes are calculated. Common items include:
- **Roth 401(k)** contributions
- **ESPP** (Employee Stock Purchase Plan)
- **After-tax 401(k)** (mega backdoor Roth)
- **Supplemental life insurance**
- **Legal services**, pet insurance, etc.

---

### Status Indicators
| Icon | Meaning | Threshold | Action |
|------|---------|-----------|--------|
| ✅ | **Pass** | ≤ $0.02 | Perfect — rounding tolerance |
| 🟡 | **Minor** | ≤ $1.00 | Acceptable — likely rounding across multiple items |
| ❌ | **Fail** | > $1.00 | Review needed — parser may have missed something |
| ⬜ | **N/A** | — | Data not available (e.g., no breakdown provided) |
            """)
        
        st.caption("**Quick Legend:** ✅ Pass | 🟡 Minor | ❌ Fail | ⬜ N/A  —  Order: `[Net][Tax][Pre][Post]`")
        
        # Create summary table showing high-level values
        st.subheader("Paystub Summary (High-Level)")
        
        summary_rows = []
        for p in paystubs:
            gross_val = p.get("gross", {}).get("value") if isinstance(p.get("gross"), dict) else p.get("gross")
            taxes_val = p.get("taxes", {}).get("value") if isinstance(p.get("taxes"), dict) else p.get("taxes")
            pretax_val = p.get("pretax_deductions", {}).get("value") if isinstance(p.get("pretax_deductions"), dict) else p.get("pretax_deductions")
            aftertax_val = p.get("aftertax_deductions", {}).get("value") if isinstance(p.get("aftertax_deductions"), dict) else p.get("aftertax_deductions")
            net_val = p.get("net_pay") if not isinstance(p.get("net_pay"), dict) else p.get("net_pay", {}).get("value")
            stock_val = p.get("stock_pay", {}).get("value") if isinstance(p.get("stock_pay"), dict) else p.get("stock_pay")
            validation_raw = p.get("validation")
            
            status_emojis, tooltip = get_validation_summary(validation_raw)
            
            summary_rows.append({
                "Pay Date": p.get("pay_date", "Unknown"),
                "Employer": p.get("employer_name", "Unknown"),
                "Gross": gross_val,
                "Taxes": taxes_val,
                "Pre-tax": pretax_val,
                "Post-tax": aftertax_val,
                "Stock": stock_val,
                "Net Pay": net_val,
                "✓ Checks": status_emojis,
                "Details": tooltip,
            })
        
        summary_df = pd.DataFrame(summary_rows)
        
        # Format currency columns
        for col in ["Gross", "Taxes", "Pre-tax", "Post-tax", "Stock", "Net Pay"]:
            if col in summary_df.columns:
                summary_df[col] = summary_df[col].apply(
                    lambda x: f"${x:,.2f}" if pd.notna(x) and x is not None else "N/A"
                )
        
        # Display with column config for tooltips
        st.dataframe(
            summary_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "✓ Checks": st.column_config.TextColumn(
                    "✓ Checks",
                    help="4 validation checks: [Net Pay Balance][Tax Sum][Pre-tax Sum][Post-tax Sum]"
                ),
                "Details": st.column_config.TextColumn(
                    "Checks Details",
                    help="Actual diff values for each check (should be ~$0.00)"
                )
            }
        )
        
        # Drill-down: Select a paystub to view details
        st.subheader("🔍 Paystub Details (Drill-Down)")
        
        pay_dates = [p.get("pay_date", "Unknown") for p in paystubs]
        selected_date = st.selectbox("Select paystub to view details:", pay_dates)
        
        selected_paystub = next((p for p in paystubs if p.get("pay_date") == selected_date), None)
        
        if selected_paystub:
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**📈 Gross Income Breakdown**")
                gross_data = selected_paystub.get("gross", {})
                if isinstance(gross_data, dict):
                    st.metric("Total Gross", f"${gross_data.get('value', 0):,.2f}")
                    details = gross_data.get("details", {})
                    if details:
                        for key, val in details.items():
                            if val and val != 0:
                                st.write(f"  • {key.replace('_', ' ').title()}: ${val:,.2f}")
                    else:
                        st.caption("No breakdown available")
                
                st.markdown("**💰 Pre-tax Deductions**")
                pretax_data = selected_paystub.get("pretax_deductions", {})
                if isinstance(pretax_data, dict):
                    st.metric("Total Pre-tax", f"${abs(pretax_data.get('value', 0) or 0):,.2f}")
                    details = pretax_data.get("details", {})
                    if details:
                        for key, val in details.items():
                            if val and val != 0:
                                st.write(f"  • {key.replace('_', ' ').title()}: ${abs(val):,.2f}")
                    else:
                        st.caption("No breakdown available")
            
            with col2:
                st.markdown("**🏛️ Taxes Breakdown**")
                taxes_data = selected_paystub.get("taxes", {})
                if isinstance(taxes_data, dict):
                    st.metric("Total Taxes", f"${abs(taxes_data.get('value', 0) or 0):,.2f}")
                    details = taxes_data.get("details", {})
                    if details:
                        for key, val in details.items():
                            if val and val != 0:
                                st.write(f"  • {key.replace('_', ' ').title()}: ${abs(val):,.2f}")
                    else:
                        st.caption("No breakdown available")
                
                st.markdown("**💳 After-tax Deductions**")
                aftertax_data = selected_paystub.get("aftertax_deductions", {})
                if isinstance(aftertax_data, dict):
                    st.metric("Total After-tax", f"${abs(aftertax_data.get('value', 0) or 0):,.2f}")
                    details = aftertax_data.get("details", {})
                    if details:
                        for key, val in details.items():
                            if val and val != 0:
                                st.write(f"  • {key.replace('_', ' ').title()}: ${abs(val):,.2f}")
                    else:
                        st.caption("No breakdown available")
            
            # Stock pay and net pay
            col3, col4, col5 = st.columns(3)
            with col3:
                stock_data = selected_paystub.get("stock_pay", {})
                if isinstance(stock_data, dict) and stock_data.get("value"):
                    st.markdown("**📊 Stock Pay**")
                    st.metric("Stock Pay", f"${stock_data.get('value', 0):,.2f}")
                    details = stock_data.get("details", {})
                    if details:
                        for key, val in details.items():
                            if val and val != 0:
                                st.write(f"  • {key.title()}: ${val:,.2f}")
            
            with col4:
                net_val = selected_paystub.get("net_pay")
                if isinstance(net_val, dict):
                    net_val = net_val.get("value")
                if net_val is not None:
                    st.markdown("**💵 Net Pay**")
                    st.metric("Net Pay", f"${net_val:,.2f}")
            
            with col5:
                val = selected_paystub.get("validation")
                if val is not None:
                    st.markdown("**✅ Validation**")
                    # Handle both dict (new format) and float (old format)
                    if isinstance(val, dict):
                        # New format with multiple checks
                        checks = []
                        all_pass = True
                        for key, label in [("net_pay_diff", "Net"), ("tax_sum_diff", "Tax"), 
                                          ("pretax_sum_diff", "Pre"), ("aftertax_sum_diff", "Post")]:
                            diff = val.get(key)
                            if diff is not None:
                                emoji = "✅" if abs(diff) <= 0.02 else ("🟡" if abs(diff) <= 1.0 else "❌")
                                checks.append(f"{emoji} {label}: ${diff:.2f}")
                                if abs(diff) > 0.02:
                                    all_pass = False
                        status = "✓ All Pass" if all_pass else "⚠️ Issues"
                        st.metric("Status", status)
                        for c in checks:
                            st.write(c)
                    else:
                        # Old format with single value
                        status = "✓ Valid" if abs(val) <= 0.02 else "⚠️ Issue"
                        st.metric("Status", status, delta=f"${val:.2f}" if abs(val) > 0.02 else None)
        
        st.divider()

    # basic controls
    years = sorted({m.split("-")[0] for m in series["month"].tolist()})
    year = st.selectbox("Year", ["All"] + years, index=0)

    if year != "All":
        series = series[series["month"].str.startswith(year)]

    # Gross Income Trend with hover details
    st.subheader("📈 Gross Income Trend")
    st.caption("Hover over points to see month-over-month change breakdown")
    
    # Build hover text with gross breakdown
    hover_texts = []
    for _, row in series.iterrows():
        hover = f"<b>{row['month']}</b><br>"
        hover += f"Gross: ${row['gross']:,.2f}<br>"
        
        # Add month-over-month change if available
        mom_change = row.get('mom_change_pct')
        mom_reason = row.get('mom_reason')
        if mom_change is not None:
            if mom_change >= 0:
                hover += f"<br>▲ +{mom_change:.1f}% vs prev month"
            else:
                hover += f"<br>▼ {mom_change:.1f}% vs prev month"
            if mom_reason:
                hover += f"<br><i>{mom_reason}</i>"
        
        # Add gross breakdown
        gross_details = row.get('gross_details', {})
        if gross_details and isinstance(gross_details, dict):
            hover += "<br><br><b>Breakdown:</b>"
            for key, val in gross_details.items():
                if val and val != 0:
                    name = key.replace("_", " ").title()
                    hover += f"<br>  • {name}: ${val:,.2f}"
        
        hover_texts.append(hover)
    
    # Create Plotly chart
    fig = go.Figure()
    
    # Add line trace
    fig.add_trace(go.Scatter(
        x=series["month"],
        y=series["gross"],
        mode="lines+markers",
        name="Gross Income",
        line=dict(color="#1f77b4", width=2),
        marker=dict(size=8),
        hovertemplate="%{customdata}<extra></extra>",
        customdata=hover_texts
    ))
    
    # Highlight significant changes (>25%)
    significant_up = series[series.get("mom_change_pct", pd.Series([None]*len(series))).apply(lambda x: x is not None and x >= 25)]
    significant_down = series[series.get("mom_change_pct", pd.Series([None]*len(series))).apply(lambda x: x is not None and x <= -25)]
    
    if len(significant_up) > 0:
        fig.add_trace(go.Scatter(
            x=significant_up["month"],
            y=significant_up["gross"],
            mode="markers",
            name="Large Increase (≥25%)",
            marker=dict(color="green", size=14, symbol="triangle-up"),
            hoverinfo="skip"
        ))
    
    if len(significant_down) > 0:
        fig.add_trace(go.Scatter(
            x=significant_down["month"],
            y=significant_down["gross"],
            mode="markers",
            name="Large Decrease (≤-25%)",
            marker=dict(color="red", size=14, symbol="triangle-down"),
            hoverinfo="skip"
        ))
    
    fig.update_layout(
        xaxis_title="Month",
        yaxis_title="Gross Income ($)",
        hovermode="closest",
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Monthly gross vs net")
    st.line_chart(series.set_index("month")[["gross", "net"]])

    st.subheader("Monthly tax total")
    st.line_chart(series.set_index("month")[["tax_total"]])

    st.subheader("Effective tax rate (tax_total / gross)")
    # streamlit line_chart ignores None poorly; fill with NaN
    series2 = series.copy()
    series2["eff_tax_rate"] = pd.to_numeric(series2["eff_tax_rate"], errors="coerce")
    st.line_chart(series2.set_index("month")[["eff_tax_rate"]])

    st.subheader("Deductions (pre-tax vs post-tax)")
    st.line_chart(series.set_index("month")[["pre_tax_deductions", "post_tax_deductions"]])

    st.subheader("Insights")
    if trends.get("insights"):
        for s in trends["insights"]:
            st.write("• " + s)
    else:
        st.write("No insights yet. Add more paystubs for stronger trend detection.")

    with st.expander("View aggregated data table"):
        st.dataframe(series, use_container_width=True)