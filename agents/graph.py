"""LangGraph definition for the Agentic Wealth Copilot.

This module wires together the various nodes that make up the
Agentic Wealth Copilot's control flow.  The graph is built using
``langgraph.graph.StateGraph`` and uses the ``CopilotState`` dataclass
to thread state through each node.  The planner chooses which domain
module to invoke based on simple keyword heuristics, then a critic
applies basic safety checks before completing the run.

The primary entry point exposed by this module is ``run_copilot``
which accepts a user message and session ID, invokes the compiled
graph, and returns the final reply along with a trace of operations.
"""

from __future__ import annotations

from langgraph.graph import StateGraph, END

from agents.state import CopilotState
from agents.nodes.planner import planner_node
from agents.nodes.income_tax import income_tax_node
from agents.nodes.wealth import wealth_node
from agents.nodes.investing import investing_node
from agents.nodes.critic import critic_node


def _route(state: CopilotState) -> str:
    """Determine which domain node to execute next based on intent.

    The planner sets ``state.intent`` to one of ``income_tax``,
    ``wealth``, ``investing``, ``general`` or ``unknown``.  This helper
    returns the intent value directly, which is used by the conditional
    edge mapping below.
    """
    return state.intent


def build_graph() -> StateGraph:
    """Construct and compile the LangGraph for the copilot.

    The graph has a single entry point (the planner) which routes to
    one of the domain nodes.  Each domain node then transitions to
    the critic before terminating.  Additional nodes and edges can be
    added as the system evolves without changing the basic topology.
    """
    g = StateGraph(CopilotState)

    # Register nodes
    g.add_node("planner", planner_node)
    g.add_node("income_tax", income_tax_node)
    g.add_node("wealth", wealth_node)
    g.add_node("investing", investing_node)
    g.add_node("critic", critic_node)

    # Define entry point
    g.set_entry_point("planner")

    # Conditional routing from planner based on intent
    g.add_conditional_edges(
        "planner",
        _route,
        {
            "income_tax": "income_tax",
            "wealth": "wealth",
            "investing": "investing",
            "general": "critic",
            "unknown": "critic",
        },
    )

    # After a domain node runs, transition to critic and then terminate
    g.add_edge("income_tax", "critic")
    g.add_edge("wealth", "critic")
    g.add_edge("investing", "critic")
    g.add_edge("critic", END)

    return g.compile()


# Compile the graph once at module import time.  LangGraph uses a
# stateful runner behind the scenes, so constructing the graph only
# once amortises the cost of compilation across calls to ``run_copilot``.
_GRAPH = build_graph()


def run_copilot(message: str, session_id: str = "default") -> tuple[str, list[str]]:
    """Execute the copilot graph for a given message and session.

    This function instantiates a ``CopilotState`` with the provided
    message and session ID, invokes the compiled LangGraph and
    returns the resulting reply and trace.  The reply is the
    ``reply`` field of the final state, and the trace contains a
    chronological list of operations performed by the nodes.

    Args:
        message: The user's input message.
        session_id: A unique identifier for the conversation.

    Returns:
        A tuple of the assistant's reply and a list of trace strings.
    """
    state = CopilotState(session_id=session_id, user_message=message)
    out: CopilotState = _GRAPH.invoke(state)
    return out.reply, out.trace
