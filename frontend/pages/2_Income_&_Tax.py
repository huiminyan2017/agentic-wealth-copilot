"""Income & Tax page.

This page will guide users through uploading W‑2 forms and paystubs,
present extracted information, visualise income trends and explain
tax concepts using personalised examples.  Currently it presents a
placeholder message.
"""

import streamlit as st


st.title("Income & Tax")
st.write(
    "This section will allow you to upload W‑2s and paystubs (kept "
    "securely on your machine), extract key fields such as wages and "
    "withholdings, plot your income over time and explain the tax "
    "implications of each deduction."
)
