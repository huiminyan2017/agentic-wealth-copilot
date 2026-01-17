"""Agent core package.

This package contains the LangGraph graph definition, state dataclass and
individual node functions for each domain.  The planner routes requests
to the appropriate domain based on intent keywords and a simple critic
performs safety checks.
"""