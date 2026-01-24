"""Investing node — stub for future rule-based trading."""

from __future__ import annotations

from agents.state import CopilotState


def investing_node(state: CopilotState) -> CopilotState:
    state.notes.append("investing:placeholder")
    state.reply = (
        "Investing/Trading module stub.\n"
        "Next: define a rule like 'MSFT >= X sell Y%' and 'MSFT <= Z buy $A'. "
        "We'll monitor prices (paper-only), simulate trades, and explain risks like taxes and whipsaw."
    )
    state.trace.append("investing:ok")
    return state
