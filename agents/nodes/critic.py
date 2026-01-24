"""Critic node — safety checks appended to every response."""

from __future__ import annotations

from agents.state import CopilotState


def critic_node(state: CopilotState) -> CopilotState:
    msg = state.user_message.lower()
    if any(k in msg for k in ["sell", "buy", "trade", "order"]):
        state.trace.append("critic:trading_safety=paper_only")
    state.trace.append("critic:ok")
    return state
