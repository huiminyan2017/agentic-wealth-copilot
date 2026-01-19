"""Income & Tax page.

This page will guide users through uploading W‑2 forms and paystubs,
present extracted information, visualise income trends and explain
tax concepts using personalised examples.  Currently it presents a
placeholder message.
"""

import streamlit as st
import pandas as pd
import re
from api import request_json

st.title("Income & Tax")

person = st.selectbox("Person", ["Huimin", "Bao"], index=0)

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

st.divider()
st.header("Income trend analytics")

if st.button("📈 Load trends"):
    try:
        trends = request_json("GET", f"/api/income/trends?person={person}")
        st.session_state["income_trends"] = trends
    except Exception as e:
        st.error(f"Failed to load trends: {e}")

trends = st.session_state.get("income_trends")
if trends:
    series = pd.DataFrame(trends["series"])

    # basic controls
    years = sorted({m.split("-")[0] for m in series["month"].tolist()})
    year = st.selectbox("Year", ["All"] + years, index=0)

    if year != "All":
        series = series[series["month"].str.startswith(year)]

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