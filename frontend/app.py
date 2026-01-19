"""Streamlit app entrypoint for the Agentic Wealth Copilot UI.

This module defines a simple chat interface on top of Streamlit that
interacts with the FastAPI backend.  It uses ``frontend.state`` to
manage per-session state and ``frontend.api`` to communicate with the
backend.  Additional pages are provided under the ``pages`` folder
which Streamlit automatically discovers.
"""

from __future__ import annotations

import streamlit as st
from state import ensure_session
from api import request_json

def main():
    st.set_page_config(
        page_title="Agentic Wealth Copilot",
        layout="wide",
    )

    ensure_session()

    st.title("💰 Agentic Wealth Copilot")
    st.caption("Your lifelong, privacy-first financial copilot")

    with st.sidebar:
        st.header("Session")
        st.write(f"Session ID: `{st.session_state.session_id}`")
        if st.button("Reset conversation"):
            st.session_state.chat_history = []
            st.experimental_rerun()

    st.divider()

    # Chat history
    for role, msg in st.session_state.chat_history:
        with st.chat_message(role):
            st.markdown(msg)

    # Input box
    user_input = st.chat_input("Ask me about your finances...")

    if user_input:
        st.session_state.chat_history.append(("user", user_input))
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    payload = {
                        "message": user_input,
                        "session_id": st.session_state.session_id,
                    }
                    resp = request_json("POST", "/api/copilot", payload)
                    answer = resp.get("reply", "(no response)")
                except Exception as e:
                    answer = f"⚠️ Error: {e}"

                st.markdown(answer)

        st.session_state.chat_history.append(("assistant", answer))


if __name__ == "__main__":
    main()
