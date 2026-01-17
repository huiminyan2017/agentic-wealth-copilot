"""Session state helpers for the Streamlit frontend.

This module provides convenience functions for managing per‑session
state in Streamlit.  A new ``session_id`` is created for each visitor
using UUIDs, and a chat history is maintained in the session state.
"""

from __future__ import annotations

import uuid
import streamlit as st


def ensure_session() -> None:
    """Initialise session variables if they are not already set.

    The ``session_id`` is used to correlate messages with the backend
    and isolate conversation state.  ``messages`` holds the history of
    chat messages exchanged between the user and the assistant.
    """
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    if "messages" not in st.session_state:
        st.session_state.messages: list[dict[str, str]] = []
