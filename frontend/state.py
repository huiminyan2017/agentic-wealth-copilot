"""Session state helpers for the Streamlit frontend.

All session state variables are initialised here so individual pages
don't need ad-hoc `if key not in st.session_state` guards.
"""

from __future__ import annotations

import uuid
import streamlit as st


def ensure_session() -> None:
    """Initialise all session variables if they are not already set."""
    defaults = {
        "session_id":            str(uuid.uuid4()),
        "chat_history":          [],
        "selected_person_index": 0,
        "person":                None,
        "income_analysis":       None,
    }
    for key, default in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default
