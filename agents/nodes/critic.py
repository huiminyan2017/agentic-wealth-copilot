"""Critic node for the copilot graph.

The critic performs simple safety and quality checks on the state before
finalizing the response.  It appends notes to the trace when potential
issues are detected (e.g. trading actions should only be simulated).
"""

from agents.state import CopilotState


def critic_node(state: CopilotState) -> CopilotState:
    # Add a warning if the user's message suggests trading; remind paper‑only.
    msg = state.user_message.lower()
    if any(k in msg for k in ["sell", "buy", "trade", "order"]):
        state.trace.append("critic:trading_safety=paper_only")

    state.trace.append("critic:ok")
    return state