"""Spending page.

This page allows users to track one-time and recurring spending,
upload receipt images for automatic extraction, and view spending analytics.
"""

import streamlit as st
import pandas as pd
import re
from datetime import date, datetime, timedelta
from pathlib import Path
import plotly.graph_objects as go
import plotly.express as px
from api import request_json, request_upload
from state import ensure_session

ensure_session()

st.title("💸 Spending")

# ---- Spending Categories ----
SPENDING_CATEGORIES = [
    "Car",
    "Clothes",
    "Education",
    "Entertainment",
    "Fees & adjustments",
    "Food & drink",
    "For Parents",
    "Gas",
    "Gifts & donations",
    "Groceries",
    "Health & wellness",
    "Home fixes & update",
    "Home Furnitures",
    "Kid toy",
    "Miscellaneous",
    "For Relatives",
    "Personal",
    "Social",
    "Tax",
    "Travel",
    "Utilities (water/gas/electric/internet/mobile)",
]

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


# Get existing people
existing_people = get_existing_people()
if not existing_people:
    st.warning("No people found. Please create a person in the Income & Tax page first.")
    st.stop()

person = st.selectbox("Person", existing_people, index=0)

# ---- Main tabs: Individual vs Overview ----
main_tab_individual, main_tab_overview = st.tabs([
    "👤 Individual", 
    "📊 Household Overview"
])

# ============================================================================
# INDIVIDUAL TAB - Per-person spending tracking
# ============================================================================
with main_tab_individual:
    # ---- Tabs for different views ----
    tab_onetime, tab_recurring, tab_analytics = st.tabs([
        "📝 One-Time Spending", 
        "🔄 Recurring Spending", 
        "📈 Analytics"
    ])

# ============================================================================
# Tab 1: One-Time Spending
# ============================================================================
with tab_onetime:
    st.subheader("One-Time Spending")
    
    # Date filter
    col_start, col_end = st.columns(2)
    with col_start:
        filter_start = st.date_input(
            "From", 
            value=date.today() - timedelta(days=30),
            key="onetime_start"
        )
    with col_end:
        filter_end = st.date_input(
            "To", 
            value=date.today(),
            key="onetime_end"
        )
    
    # Load spending data
    if st.button("🔄 Refresh", key="refresh_onetime"):
        st.rerun()
    
    try:
        params = f"?person={person}"
        if filter_start:
            params += f"&start_date={filter_start.isoformat()}"
        if filter_end:
            params += f"&end_date={filter_end.isoformat()}"
        
        response = request_json("GET", f"/api/spending/list{params}")
        spending_items = response.get("items", [])
    except Exception as e:
        spending_items = []
        if "Connection refused" not in str(e):
            st.error(f"Error loading spending: {e}")
    
    # Check for suspected duplicates
    try:
        dup_response = request_json("GET", f"/api/spending/duplicates?person={person}")
        duplicate_groups = dup_response.get("duplicate_groups", [])
        if duplicate_groups:
            with st.expander(f"⚠️ **{len(duplicate_groups)} Suspected Duplicate Group(s) Found** - Click to review", expanded=True):
                st.warning("The following items have the same date, amount, and merchant. Please review and delete any duplicates.")
                for i, group in enumerate(duplicate_groups):
                    st.markdown(f"**Group {i+1}:** {group[0]['date']} | ${group[0]['amount']:.2f} | {group[0].get('merchant', 'Unknown')}")
                    for item in group:
                        cols = st.columns([3, 1])
                        with cols[0]:
                            st.text(f"  • {item.get('description', 'No description')} (ID: {item['id'][:8]}...)")
                        with cols[1]:
                            if st.button("🗑️ Delete", key=f"dup_del_{item['id']}"):
                                try:
                                    request_json("DELETE", f"/api/spending/{item['id']}?person={person}")
                                    st.success("Deleted!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error: {e}")
                    st.divider()
    except Exception:
        pass  # Silently ignore if endpoint not available
    
    # Add new spending form
    with st.expander("➕ Add New Spending", expanded=False):
        with st.form("add_spending_form"):
            col1, col2 = st.columns(2)
            with col1:
                new_date = st.date_input("Date", value=date.today(), key="new_date")
                new_what = st.selectbox("Category", options=SPENDING_CATEGORIES, index=SPENDING_CATEGORIES.index("Miscellaneous"))
                new_merchant = st.text_input("Merchant", placeholder="e.g., Costco, Amazon, Walmart")
            with col2:
                new_amount = st.number_input("Amount ($)", step=0.01, format="%.2f", help="Negative for refunds")
                new_qty = st.number_input("Quantity", min_value=1, value=1, step=1, key="new_qty")
                new_desc = st.text_input("Description", placeholder="Optional details")
            
            if st.form_submit_button("💾 Save", type="primary"):
                if new_what and new_amount != 0:
                    try:
                        result = request_json("POST", f"/api/spending?person={person}", {
                            "date": new_date.isoformat(),
                            "what": new_what,
                            "amount": new_amount,
                            "quantity": new_qty,
                            "merchant": new_merchant or None,
                            "description": new_desc or None,
                            "source": "manual"
                        })
                        st.success(f"✅ Added ${new_amount:.2f} for {new_what}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error saving: {e}")
                else:
                    st.warning("Please enter category and amount")
    
    # Display spending table
    if spending_items:
        # Calculate total
        total = sum(item.get("amount", 0) for item in spending_items)
        st.metric("Total Spending", f"${total:,.2f}", delta=f"{len(spending_items)} transactions")
        
        # Header row
        header_cols = st.columns([1.1, 1.1, 0.8, 0.6, 1.3, 2.2, 0.7, 1])
        with header_cols[0]:
            st.markdown("**Date**")
        with header_cols[1]:
            st.markdown("**Category**")
        with header_cols[2]:
            st.markdown("**Amount**")
        with header_cols[3]:
            st.markdown("**Qty**")
        with header_cols[4]:
            st.markdown("**Merchant**")
        with header_cols[5]:
            st.markdown("**Description**")
        with header_cols[6]:
            st.markdown("**Source**")
        with header_cols[7]:
            st.markdown("**Actions**")
        st.divider()
        
        # Display items with inline edit/delete buttons
        for idx, item in enumerate(spending_items):
            with st.container():
                cols = st.columns([1.1, 1.1, 0.8, 0.6, 1.3, 2.2, 0.7, 1])
                
                with cols[0]:
                    st.text(item.get("date", ""))
                with cols[1]:
                    st.text(item.get("what", ""))
                with cols[2]:
                    st.text(f"${item.get('amount', 0):,.2f}")
                with cols[3]:
                    st.text(str(item.get("quantity", 1)))
                with cols[4]:
                    st.text(item.get("merchant", "") or "")
                with cols[5]:
                    st.text(item.get("description", "") or "")
                with cols[6]:
                    st.text(item.get("source", "manual"))
                with cols[7]:
                    col_edit, col_del = st.columns(2)
                    with col_edit:
                        if st.button("✏️", key=f"edit_{item['id']}", help="Edit"):
                            st.session_state[f"editing_{item['id']}"] = True
                    with col_del:
                        if st.button("🗑️", key=f"del_{item['id']}", help="Delete"):
                            try:
                                request_json("DELETE", f"/api/spending/{item['id']}?person={person}")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")
                
                # Edit form (appears when edit button clicked)
                if st.session_state.get(f"editing_{item['id']}", False):
                    with st.form(key=f"edit_form_{item['id']}"):
                        st.caption("Edit Spending")
                        edit_cols = st.columns([1, 1, 0.8, 0.6, 1.2, 2])
                        with edit_cols[0]:
                            edit_date = st.date_input("Date", value=date.fromisoformat(item["date"]), key=f"ed_{item['id']}")
                        with edit_cols[1]:
                            # Get index of current category, default to Miscellaneous if not found
                            current_cat = item.get("what", "Miscellaneous")
                            cat_idx = SPENDING_CATEGORIES.index(current_cat) if current_cat in SPENDING_CATEGORIES else SPENDING_CATEGORIES.index("Miscellaneous")
                            edit_what = st.selectbox("Category", options=SPENDING_CATEGORIES, index=cat_idx, key=f"ew_{item['id']}")
                        with edit_cols[2]:
                            edit_amount = st.number_input("Amount", value=float(item.get("amount", 0)), step=0.01, key=f"ea_{item['id']}")
                        with edit_cols[3]:
                            edit_qty = st.number_input("Qty", value=int(item.get("quantity", 1)), min_value=1, step=1, key=f"eq_{item['id']}")
                        with edit_cols[4]:
                            edit_merchant = st.text_input("Merchant", value=item.get("merchant", "") or "", key=f"em_{item['id']}")
                        with edit_cols[5]:
                            edit_desc = st.text_input("Description", value=item.get("description", "") or "", key=f"edesc_{item['id']}")
                        
                        col_save, col_cancel = st.columns(2)
                        with col_save:
                            if st.form_submit_button("💾 Save"):
                                try:
                                    request_json("PUT", f"/api/spending/{item['id']}?person={person}", {
                                        "date": edit_date.isoformat(),
                                        "what": edit_what,
                                        "amount": edit_amount,
                                        "quantity": edit_qty,
                                        "merchant": edit_merchant or None,
                                        "description": edit_desc or None
                                    })
                                    del st.session_state[f"editing_{item['id']}"]
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error: {e}")
                        with col_cancel:
                            if st.form_submit_button("❌ Cancel"):
                                del st.session_state[f"editing_{item['id']}"]
                                st.rerun()
                
                st.divider()
    else:
        st.info("No spending records found for this period. Add your first spending above or upload a receipt!")
    
    # ---- Upload Receipts Section ----
    st.divider()
    st.subheader("📷 Upload Receipts")
    st.caption("Upload receipt photos or PDFs and we'll extract the spending details automatically")
    
    # Use a counter to reset the file uploader after successful save
    if "receipt_uploader_key" not in st.session_state:
        st.session_state["receipt_uploader_key"] = 0
    
    # File uploader
    uploaded_files = st.file_uploader(
        "Upload receipt images or PDFs",
        type=["jpg", "jpeg", "png", "gif", "webp", "pdf"],
        accept_multiple_files=True,
        help="Upload one or more receipt images or PDF files",
        key=f"onetime_receipt_upload_{st.session_state['receipt_uploader_key']}"
    )
    
    default_receipt_date = st.date_input(
        "Default date (if not found on receipt)",
        value=date.today(),
        key="receipt_default_date"
    )
    
    if uploaded_files:
        st.write(f"📎 {len(uploaded_files)} file(s) selected")
        
        if st.button("🔍 Parse Receipts", type="primary", key="parse_receipts_btn"):
            all_extracted = []
            
            for uploaded_file in uploaded_files:
                with st.spinner(f"Parsing {uploaded_file.name}..."):
                    try:
                        # Call the receipt parsing API
                        result = request_upload(
                            "/api/spending/parse-receipt",
                            file=uploaded_file,
                            data={
                                "person": person,
                                "default_date": default_receipt_date.isoformat(),
                            }
                        )
                        
                        if result.get("items"):
                            all_extracted.extend(result["items"])
                            # Calculate total of extracted items
                            items_total = sum(item.get("amount", 0) for item in result["items"])
                            st.success(f"✅ Extracted {len(result['items'])} item(s) from {uploaded_file.name} — Total: ${items_total:,.2f}")
                            # Show date extraction info and any warnings
                            for warn in result.get("warnings", []):
                                if "Extracted date" in warn:
                                    st.info(f"📅 {warn}")
                                elif "mismatch" in warn.lower():
                                    st.warning(warn)
                                elif "verified" in warn.lower():
                                    st.success(warn)
                        else:
                            warnings = result.get("warnings", [])
                            if warnings:
                                st.warning(f"⚠️ {uploaded_file.name}: {warnings[0]}")
                            else:
                                st.warning(f"⚠️ No items found in {uploaded_file.name}")
                        
                        # Show raw text for debugging if available
                        if result.get("raw_text"):
                            with st.expander(f"Show raw OCR text for {uploaded_file.name}"):
                                st.code(result["raw_text"])
                            
                    except Exception as e:
                        st.error(f"Error parsing {uploaded_file.name}: {e}")
            
            # Store extracted items in session state for review
            if all_extracted:
                st.session_state["pending_receipts"] = all_extracted
    
    # Review and confirm extracted items
    if "pending_receipts" in st.session_state and st.session_state["pending_receipts"]:
        st.divider()
        st.subheader("Review Extracted Items")
        st.caption("Edit or remove items before saving")
        
        pending = st.session_state["pending_receipts"]
        
        # Display as editable form
        items_to_save = []
        for i, item in enumerate(pending):
            with st.container():
                col1, col2, col3, col4, col5, col6 = st.columns([1.3, 1.3, 1.3, 1.5, 0.7, 0.7])
                with col1:
                    edit_date = st.date_input(
                        "Date",
                        value=date.fromisoformat(item["date"]) if isinstance(item["date"], str) else item["date"],
                        key=f"edit_date_{i}"
                    )
                with col2:
                    edit_merchant = st.text_input("Merchant", value=item.get("merchant") or "", key=f"edit_merchant_{i}")
                with col3:
                    # Get index of current category, default to Miscellaneous if not found
                    current_cat = item["what"]
                    cat_idx = SPENDING_CATEGORIES.index(current_cat) if current_cat in SPENDING_CATEGORIES else SPENDING_CATEGORIES.index("Miscellaneous")
                    edit_what = st.selectbox("Category", options=SPENDING_CATEGORIES, index=cat_idx, key=f"edit_what_{i}")
                with col4:
                    edit_amount = st.number_input(
                        "Amount",
                        value=float(item["amount"]),
                        step=0.01,
                        format="%.2f",
                        key=f"edit_amount_{i}"
                    )
                with col5:
                    edit_qty = st.number_input("Qty", value=int(item.get("quantity", 1)), min_value=1, step=1, key=f"edit_qty_{i}")
                with col6:
                    keep_item = st.checkbox("Keep", value=True, key=f"keep_{i}")
                
                edit_desc = st.text_input(
                    "Description",
                    value=item.get("description") or "",
                    key=f"edit_desc_{i}"
                )
                
                if keep_item:
                    items_to_save.append({
                        "date": edit_date.isoformat(),
                        "merchant": edit_merchant or None,
                        "what": edit_what,
                        "amount": edit_amount,
                        "quantity": edit_qty,
                        "description": edit_desc or None,
                        "source": "receipt",
                        "receipt_path": item.get("receipt_path"),
                    })
                
                st.divider()
        
        # Show live total of items to save
        live_total = sum(item["amount"] for item in items_to_save)
        removed_count = len(pending) - len(items_to_save)
        
        col_total, col_info = st.columns([1, 2])
        with col_total:
            st.metric("Items to Save", f"{len(items_to_save)} items", delta=f"-{removed_count}" if removed_count > 0 else None)
        with col_info:
            st.metric("Total Amount", f"${live_total:,.2f}")
        
        col_save, col_clear = st.columns(2)
        with col_save:
            if st.button("💾 Save All", type="primary", disabled=len(items_to_save) == 0, key="save_receipts_btn"):
                try:
                    result = request_json("POST", f"/api/spending/batch?person={person}", {
                        "items": items_to_save
                    })
                    created = result.get("created", [])
                    skipped = result.get("duplicates_skipped", 0)
                    
                    if created:
                        st.success(f"✅ Saved {len(created)} spending records!")
                    if skipped > 0:
                        st.info(f"ℹ️ Skipped {skipped} duplicate item(s)")
                    if not created and skipped > 0:
                        st.warning("All items were duplicates - nothing new to save.")
                    
                    # Clear pending receipts and reset file uploader
                    del st.session_state["pending_receipts"]
                    st.session_state["receipt_uploader_key"] += 1  # Reset file uploader
                    st.rerun()
                except Exception as e:
                    st.error(f"Error saving: {e}")
        
        with col_clear:
            if st.button("🗑️ Clear All", key="clear_receipts_btn"):
                del st.session_state["pending_receipts"]
                st.session_state["receipt_uploader_key"] += 1  # Reset file uploader
                st.rerun()


# ============================================================================
# Tab 2: Recurring Spending
# ============================================================================
with tab_recurring:
    st.subheader("Recurring Spending")
    st.caption("Track subscriptions, rent, utilities, and other periodic expenses")
    
    # Load recurring data
    try:
        response = request_json("GET", f"/api/spending/recurring/list?person={person}")
        recurring_items = response.get("items", [])
        monthly_total = response.get("monthly_total", 0)
    except Exception as e:
        recurring_items = []
        monthly_total = 0
        if "Connection refused" not in str(e):
            st.error(f"Error loading recurring spending: {e}")
    
    # Add new recurring form
    with st.expander("➕ Add Recurring Expense", expanded=False):
        with st.form("add_recurring_form"):
            col1, col2 = st.columns(2)
            with col1:
                rec_what = st.text_input("Name", placeholder="e.g., Netflix, Rent, Gym")
                rec_amount = st.number_input("Amount ($)", step=0.01, format="%.2f", key="rec_amount", help="Negative for credits")
            with col2:
                rec_freq = st.selectbox("Frequency", ["monthly", "weekly", "biweekly", "quarterly", "yearly", "daily"])
                rec_start = st.date_input("Start Date", value=date.today(), key="rec_start")
            
            rec_desc = st.text_input("Description", placeholder="Optional notes", key="rec_desc")
            
            if st.form_submit_button("💾 Save Recurring", type="primary"):
                if rec_what and rec_amount != 0:
                    try:
                        result = request_json("POST", f"/api/spending/recurring?person={person}", {
                            "what": rec_what,
                            "amount": rec_amount,
                            "frequency": rec_freq,
                            "start_date": rec_start.isoformat(),
                            "description": rec_desc or None,
                        })
                        st.success(f"✅ Added recurring: {rec_what}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error saving: {e}")
                else:
                    st.warning("Please enter name and amount")
    
    # Display recurring table
    if recurring_items:
        st.metric("Monthly Total", f"${monthly_total:,.2f}", delta=f"{len(recurring_items)} recurring expenses")
        
        # Display as cards
        for item in recurring_items:
            with st.container():
                col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
                with col1:
                    status = "🟢" if item.get("is_active", True) else "🔴"
                    st.write(f"{status} **{item['what']}**")
                    if item.get("description"):
                        st.caption(item["description"])
                with col2:
                    st.write(f"${item['amount']:.2f}")
                with col3:
                    st.write(item["frequency"].capitalize())
                with col4:
                    if st.button("🗑️", key=f"del_rec_{item['id']}"):
                        try:
                            request_json("DELETE", f"/api/spending/recurring/{item['id']}?person={person}")
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))
                st.divider()
    else:
        st.info("No recurring expenses set up. Add your subscriptions and bills above!")


# ============================================================================
# Tab 3: Analytics
# ============================================================================
with tab_analytics:
    st.subheader("Spending Analytics")
    
    # Date range for analytics
    col_start, col_end = st.columns(2)
    with col_start:
        analytics_start = st.date_input(
            "From",
            value=date.today().replace(day=1) - timedelta(days=90),
            key="analytics_start"
        )
    with col_end:
        analytics_end = st.date_input(
            "To",
            value=date.today(),
            key="analytics_end"
        )
    
    try:
        # Get summary
        params = f"?person={person}"
        if analytics_start:
            params += f"&start_date={analytics_start.isoformat()}"
        if analytics_end:
            params += f"&end_date={analytics_end.isoformat()}"
        
        summary = request_json("GET", f"/api/spending/summary{params}")
        
        # Key metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total One-Time", f"${summary.get('total_one_time', 0):,.2f}")
        with col2:
            st.metric("Monthly Recurring", f"${summary.get('monthly_recurring', 0):,.2f}")
        with col3:
            st.metric("Total Records", summary.get("total_records", 0))
        
        # Category breakdown chart
        by_category = summary.get("by_category", {})
        if by_category:
            st.subheader("Spending by Category")
            
            # Pie chart
            fig = px.pie(
                names=list(by_category.keys()),
                values=list(by_category.values()),
                title="Category Breakdown"
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # Bar chart
            fig2 = px.bar(
                x=list(by_category.keys()),
                y=list(by_category.values()),
                labels={"x": "Category", "y": "Amount ($)"},
                title="Spending by Category"
            )
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No spending data available for the selected period.")
            
    except Exception as e:
        if "Connection refused" not in str(e):
            st.error(f"Error loading analytics: {e}")
        else:
            st.warning("Backend not available. Start the backend to see analytics.")

# ============================================================================
# OVERVIEW TAB - Household spending across all people
# ============================================================================
with main_tab_overview:
    st.subheader("Household Spending Overview")
    st.caption("Consolidated spending view across all household members")
    
    # ---- Date Range Filter ----
    date_range = st.selectbox(
        "Date Range",
        ["Last 30 days", "Last 90 days", "Last 6 months", "Last year", "All time", "Custom"],
        index=0,
        key="overview_date_range"
    )
    
    today = date.today()
    if date_range == "Last 30 days":
        start_date = today - timedelta(days=30)
        end_date = today
    elif date_range == "Last 90 days":
        start_date = today - timedelta(days=90)
        end_date = today
    elif date_range == "Last 6 months":
        start_date = today - timedelta(days=180)
        end_date = today
    elif date_range == "Last year":
        start_date = today - timedelta(days=365)
        end_date = today
    elif date_range == "All time":
        start_date = date(2020, 1, 1)
        end_date = today
    else:  # Custom
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("From", value=today - timedelta(days=30), key="overview_start")
        with col2:
            end_date = st.date_input("To", value=today, key="overview_end")
    
    # Person filter (multi-select)
    selected_people = st.multiselect(
        "Include People",
        options=existing_people,
        default=existing_people,
        help="Select which people to include in the overview"
    )
    
    if not selected_people:
        st.warning("Please select at least one person.")
        st.stop()
    
    # ---- Load Data ----
    @st.cache_data(ttl=60)
    def load_overview_data(people: list, start: date, end: date) -> pd.DataFrame:
        """Load spending data for multiple people."""
        all_records = []
        
        for p in people:
            try:
                params = f"?person={p}"
                if start:
                    params += f"&start_date={start.isoformat()}"
                if end:
                    params += f"&end_date={end.isoformat()}"
                
                response = request_json("GET", f"/api/spending/list{params}")
                items = response.get("items", [])
                
                for item in items:
                    item["person"] = p
                    all_records.append(item)
            except Exception as e:
                st.error(f"Error loading {p}: {e}")
        
        if not all_records:
            return pd.DataFrame()
        
        df = pd.DataFrame(all_records)
        df["date"] = pd.to_datetime(df["date"])
        df["amount"] = df["amount"].astype(float)
        return df
    
    # Load data
    with st.spinner("Loading spending data..."):
        df = load_overview_data(selected_people, start_date, end_date)
    
    if df.empty:
        st.info("No spending records found for the selected period and people.")
        st.stop()
    
    # ---- Summary Metrics ----
    st.markdown("### Summary")
    
    col1, col2, col3, col4 = st.columns(4)
    
    total_spending = df["amount"].sum()
    num_transactions = len(df)
    avg_transaction = df["amount"].mean()
    num_categories = df["what"].nunique()
    
    with col1:
        st.metric("Total Spending", f"${total_spending:,.2f}")
    with col2:
        st.metric("Transactions", f"{num_transactions:,}")
    with col3:
        st.metric("Avg Transaction", f"${avg_transaction:,.2f}")
    with col4:
        st.metric("Categories", f"{num_categories}")
    
    st.divider()
    
    # ---- Per-Person Breakdown ----
    st.markdown("### Spending by Person")
    
    col_table, col_chart = st.columns([1, 2])
    
    with col_table:
        person_summary = df.groupby("person").agg(
            Total=("amount", "sum"),
            Transactions=("amount", "count"),
            Average=("amount", "mean")
        ).round(2)
        person_summary["Total"] = person_summary["Total"].apply(lambda x: f"${x:,.2f}")
        person_summary["Average"] = person_summary["Average"].apply(lambda x: f"${x:,.2f}")
        st.dataframe(person_summary, use_container_width=True)
    
    with col_chart:
        person_totals = df.groupby("person")["amount"].sum().reset_index()
        fig = px.pie(
            person_totals, 
            values="amount", 
            names="person",
            title="Spending Distribution",
            hole=0.4
        )
        fig.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig, use_container_width=True)
    
    st.divider()
    
    # ---- Category Breakdown ----
    st.markdown("### Spending by Category")
    
    col_cat_table, col_cat_chart = st.columns([1, 2])
    
    with col_cat_table:
        category_summary = df.groupby("what").agg(
            Total=("amount", "sum"),
            Count=("amount", "count")
        ).sort_values("Total", ascending=False).round(2)
        category_summary["Total"] = category_summary["Total"].apply(lambda x: f"${x:,.2f}")
        st.dataframe(category_summary, use_container_width=True)
    
    with col_cat_chart:
        category_totals = df.groupby("what")["amount"].sum().reset_index()
        category_totals = category_totals.sort_values("amount", ascending=True).tail(10)
        
        fig = px.bar(
            category_totals,
            x="amount",
            y="what",
            orientation="h",
            title="Top Categories by Spending",
            labels={"amount": "Amount ($)", "what": "Category"}
        )
        fig.update_layout(yaxis={'categoryorder': 'total ascending'})
        st.plotly_chart(fig, use_container_width=True)
    
    st.divider()
    
    # ---- Spending Over Time ----
    st.markdown("### Spending Over Time")
    
    # Daily spending by person
    daily_df = df.groupby([df["date"].dt.date, "person"])["amount"].sum().reset_index()
    daily_df.columns = ["date", "person", "amount"]
    
    fig = px.line(
        daily_df,
        x="date",
        y="amount",
        color="person",
        title="Daily Spending Trend",
        labels={"amount": "Amount ($)", "date": "Date", "person": "Person"}
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # Monthly spending comparison
    monthly_df = df.copy()
    monthly_df["month"] = monthly_df["date"].dt.to_period("M").astype(str)
    monthly_summary = monthly_df.groupby(["month", "person"])["amount"].sum().reset_index()
    
    if len(monthly_summary["month"].unique()) > 1:
        fig = px.bar(
            monthly_summary,
            x="month",
            y="amount",
            color="person",
            title="Monthly Spending by Person",
            labels={"amount": "Amount ($)", "month": "Month", "person": "Person"},
            barmode="group"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    st.divider()
    
    # ---- Top Merchants ----
    st.markdown("### Top Merchants")
    
    if "merchant" in df.columns:
        merchant_df = df[df["merchant"].notna() & (df["merchant"] != "")]
        if not merchant_df.empty:
            merchant_summary = merchant_df.groupby("merchant").agg(
                Total=("amount", "sum"),
                Visits=("amount", "count")
            ).sort_values("Total", ascending=False).head(15).round(2)
            
            col_m1, col_m2 = st.columns([1, 2])
            
            with col_m1:
                display_df = merchant_summary.copy()
                display_df["Total"] = display_df["Total"].apply(lambda x: f"${x:,.2f}")
                st.dataframe(display_df, use_container_width=True)
            
            with col_m2:
                top_merchants = merchant_df.groupby("merchant")["amount"].sum().reset_index()
                top_merchants = top_merchants.sort_values("amount", ascending=True).tail(10)
                
                fig = px.bar(
                    top_merchants,
                    x="amount",
                    y="merchant",
                    orientation="h",
                    title="Top 10 Merchants by Spending",
                    labels={"amount": "Amount ($)", "merchant": "Merchant"}
                )
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No merchant data available.")
    
    st.divider()
    
    # ---- Export ----
    st.markdown("### Export Data")
    
    col_exp1, col_exp2 = st.columns(2)
    
    with col_exp1:
        csv = df.to_csv(index=False)
        st.download_button(
            label="📥 Download as CSV",
            data=csv,
            file_name=f"spending_overview_{start_date}_{end_date}.csv",
            mime="text/csv"
        )
    
    with col_exp2:
        summary_text = f"""Spending Overview Report
Generated: {date.today().isoformat()}
Period: {start_date} to {end_date}
People: {', '.join(selected_people)}

SUMMARY
-------
Total Spending: ${total_spending:,.2f}
Transactions: {num_transactions}
Average Transaction: ${avg_transaction:,.2f}
Categories: {num_categories}

BY PERSON
---------
"""
        for p in selected_people:
            p_total = df[df["person"] == p]["amount"].sum()
            p_count = len(df[df["person"] == p])
            summary_text += f"{p}: ${p_total:,.2f} ({p_count} transactions)\n"
        
        st.download_button(
            label="📄 Download Summary Report",
            data=summary_text,
            file_name=f"spending_summary_{start_date}_{end_date}.txt",
            mime="text/plain"
        )