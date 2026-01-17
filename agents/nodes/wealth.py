"""Wealth module node.

Placeholder implementation for tracking assets and computing net worth.
Future versions will store user assets in a local database, calculate
liabilities, and compute trends and compositions.
"""

from agents.state import CopilotState


def wealth_node(state: CopilotState) -> CopilotState:
    state.notes.append("wealth:placeholder")
    state.reply = (
        "Wealth module stub.\n"
        "Next: add your assets (cash, brokerage, retirement) and liabilities "
        "(mortgage, loans) into a local‑only store, then we'll compute family net worth and trends."
    )
    state.trace.append("wealth:ok")
    return state