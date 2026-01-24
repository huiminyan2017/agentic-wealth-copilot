"""Copilot Chat page — natural language interface over all financial modules."""

from __future__ import annotations

import sys
from pathlib import Path
import streamlit as st

# Allow importing from agents/ when running via Streamlit
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from state import ensure_session
from api import request_json
try:
    from agents.llm import LLM_CONFIG_ERROR_PREFIX
except ImportError:
    LLM_CONFIG_ERROR_PREFIX = "LLM_CONFIG_ERROR"


def main():
    ensure_session()

    st.title("Copilot")
    st.caption("Ask questions about your finances, get insights, and plan your wealth journey")

    if st.button("🔄 Reset conversation"):
        st.session_state.chat_history = []
        st.rerun()

    st.divider()

    # Chat history
    for role, msg in st.session_state.chat_history:
        with st.chat_message(role):
            if role == "assistant" and msg.startswith(LLM_CONFIG_ERROR_PREFIX + ":"):
                st.error(msg.removeprefix("LLM_CONFIG_ERROR:").strip())
            else:
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

                if answer.startswith("LLM_CONFIG_ERROR:"):
                    st.error(answer.removeprefix(LLM_CONFIG_ERROR_PREFIX + ":").strip())
                else:
                    st.markdown(answer)

        st.session_state.chat_history.append(("assistant", answer))


main()
