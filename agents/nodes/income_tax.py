"""Income and tax module node.

Currently this node is a placeholder.  Future implementations will
extract key fields from W‑2 and paystub documents, compute trends and
retrieve explanations using a knowledge base.  For now it returns a
template response and records a trace entry.
"""

from agents.state import CopilotState


def income_tax_node(state: CopilotState) -> CopilotState:
    state.notes.append("income_tax:placeholder")
    state.reply = (
        "Income/Tax module stub.\n"
        "Next: upload a W‑2 or paystub (kept in data/raw, never committed), "
        "then we'll extract key fields and explain each withholding and deduction."
    )
    state.trace.append("income_tax:ok")
    return state