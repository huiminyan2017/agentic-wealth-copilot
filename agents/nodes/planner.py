"""Planner node for the copilot graph.

The planner inspects the user's message and determines which domain module
should handle the request.  It populates the ``intent`` and a list of
high‑level actions (``plan``) to be executed.  This logic is deliberately
simple and keyword‑based for the initial scaffold.
"""

from agents.state import CopilotState


def planner_node(state: CopilotState) -> CopilotState:
    msg = state.user_message.lower()

    # Very naive keyword routing.  Expand this logic as you add more
    # sophisticated classifiers or NLU components.
    if any(k in msg for k in ["w2", "paystub", "withholding", "tax"]):
        state.intent = "income_tax"
        state.plan = ["extract_income_tax", "explain_tax_basics"]
    elif any(k in msg for k in ["net worth", "wealth", "property", "mortgage", "savings"]):
        state.intent = "wealth"
        state.plan = ["aggregate_assets", "compute_trend"]
    elif any(k in msg for k in ["sell", "buy", "threshold", "trading", "rebalance"]):
        state.intent = "investing"
        state.plan = ["evaluate_rules", "simulate_action", "explain_risks"]
    else:
        state.intent = "general"
        state.plan = ["clarify_goal", "suggest_next_steps"]

    state.trace.append(f"planner:intent={state.intent}")
    return state