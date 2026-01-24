"""State dataclass for the copilot graph.

Each invocation of the LangGraph agent carries a ``CopilotState`` which
includes the user's session ID, their message, the identified intent,
notes, the final reply and a trace of intermediate
operations.  Nodes in the graph read and mutate this state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class CopilotState:
    """Container for information passed through the graph."""

    session_id: str       # Unique ID for the conversation turn
    user_message: str     # Raw message from the user, unchanged throughout the graph

    # Set by routing node
    person: Optional[str] = None              # First person name extracted from the message; None if not mentioned
    intent: str = "unknown"                   # Primary routing decision: income_tax | wealth | investing | general | unknown
    sub_intent: List[str] = field(default_factory=list)  # Finer-grained goal within the intent (e.g. "tax optimisation suggestions"); at most one entry

    # Set by domain nodes
    notes: List[str] = field(default_factory=list)  # Structured facts gathered mid-graph (e.g. "people:Alice,Bob")
    reply: str = ""                                  # Final answer returned to the user; written by the domain node, optionally amended by critic

    # Diagnostics
    trace: List[str] = field(default_factory=list)  # Ordered log of node steps, e.g. ["routing:llm:intent=income_tax", "income_tax:ok", "critic:ok"]