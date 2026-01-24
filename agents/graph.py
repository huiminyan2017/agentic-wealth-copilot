"""LangGraph orchestrator for the Agentic Wealth Copilot.

Wires all nodes together and exposes run_copilot() as the single entry
point called by the backend copilot route.
"""

from __future__ import annotations

from langgraph.graph import StateGraph, END

from agents.state import CopilotState
from agents.nodes.routing import routing_node
from agents.nodes.general_questions import general_node
from agents.nodes.income_tax import income_tax_node
from agents.nodes.wealth import wealth_node
from agents.nodes.investing import investing_node
from agents.nodes.critic import critic_node


def _route(state: CopilotState) -> str:
    return state.intent


def _build() -> StateGraph:
    g = StateGraph(CopilotState)

    g.add_node("routing",    routing_node)
    g.add_node("income_tax", income_tax_node)
    g.add_node("wealth",     wealth_node)
    g.add_node("investing",  investing_node)
    g.add_node("general",    general_node)
    g.add_node("critic",     critic_node)

    g.set_entry_point("routing")
    g.add_conditional_edges(
        "routing", _route,
        {
            "income_tax": "income_tax",
            "wealth":     "wealth",
            "investing":  "investing",
            "general":    "general",
            "unknown":    "general",
        },
    )
    for node in ("income_tax", "wealth", "investing", "general"):
        g.add_edge(node, "critic")
    g.add_edge("critic", END)

    return g.compile()


_GRAPH = _build()


def run_copilot(message: str, session_id: str = "default") -> tuple[str, list[str]]:
    """Execute the copilot graph and return (reply, trace)."""
    state = CopilotState(session_id=session_id, user_message=message)
    out = _GRAPH.invoke(state)
    if isinstance(out, dict):
        return out.get("reply", ""), out.get("trace", [])
    return out.reply, out.trace
