"""Agentic Wealth Copilot — Streamlit entrypoint.

Defines the app navigation structure using st.navigation() so every page
has a proper name and the copilot sits at the top as the primary interface.
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="Wealth Copilot",
    page_icon="💼",
    layout="wide",
)

pg = st.navigation(
    {
        "Copilot": [
            st.Page("pages/copilot.py", title="Copilot Chat", icon="💬", default=True),
        ],
        "Modules": [
            st.Page("pages/1_Income_&_Tax.py",        title="Income & Tax",       icon="🧾"),
            st.Page("pages/4_Spending.py",            title="Spending",           icon="💸"),
            st.Page("pages/2_Wealth_&_Planning.py",   title="Wealth & Planning",  icon="🏦"),
            st.Page("pages/3_Investing_&_Trading.py", title="Investing & Trading",icon="📈"),
        ],
    }
)

pg.run()
