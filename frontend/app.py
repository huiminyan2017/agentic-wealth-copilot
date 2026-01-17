"""Streamlit app entrypoint for the Agentic Wealth Copilot UI.

This module defines a simple chat interface on top of Streamlit that
interacts with the FastAPI backend.  It uses ``frontend.state`` to
manage per-session state and ``frontend.api`` to communicate with the
backend.  Additional pages are provided under the ``pages`` folder
which Streamlit automatically discovers.
"""

from __future__ import annotations

import streamlit as st

from frontend.state import ensure_session
from frontend.api import copilot


def main() -> None:
    """Render the main chat interface and handle user input."""
    # Set page configuration
    st.set_page_config(page_title="Agentic Wealth Copilot", layout="wide")
    ensure_session()

    st.title("Agentic Wealth Copilot")
    st.caption(
        "Local‑first WebUI. Paper‑only trading. Privacy‑first data handling."
    )

    # Sidebar with session info and actions
    with st.sidebar:
        st.subheader("Session")
        st.code(st.session_state.session_id)
        if st.button("Clear chat"):
            st.session_state.messages = []
            st.rerun()

    # Render chat history
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    # Input box for the user to type a message
    prompt = st.chat_input(
        "Ask about income/taxes, net worth, investing rules…",
        key="chat_input",
    )
    if prompt:
        # Append user message to history
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Call backend and display reply
        with st.chat_message("assistant"):
            try:
                resp = copilot(prompt, session_id=st.session_state.session_id)
                reply = resp.get("reply", "")
                trace = resp.get("trace", [])
                st.markdown(reply)
                # Show internal trace for debugging if available
                if trace:
                    with st.expander("Trace"):
                        st.write(trace)
            except Exception as exc:
                st.error(f"Backend error: {exc}")
                reply = ""

        # Append assistant reply to history
        st.session_state.messages.append(
            {"role": "assistant", "content": reply}
        )


if __name__ == "__main__":
    main()
