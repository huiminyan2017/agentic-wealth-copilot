"""State dataclass for the copilot graph.

Each invocation of the LangGraph agent carries a ``CopilotState`` which
includes the user's session ID, their message, the identified intent,
planned actions, notes, the final reply and a trace of intermediate
operations.  Nodes in the graph read and mutate this state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class CopilotState:
    """Container for information passed through the graph."""

    session_id: str
    user_message: str
    intent: str = "unknown"
    plan: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    reply: str = ""
    trace: List[str] = field(default_factory=list)