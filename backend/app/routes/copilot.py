"""Copilot API endpoint.

This route accepts user messages, runs the agentic workflow and returns the
assistant's reply along with a trace of the operations performed.  Before
processing, it applies simple redactions to the input to mask obvious
identifiers such as SSNs or EINs.
"""

from fastapi import APIRouter

from backend.app.schemas import CopilotRequest, CopilotResponse
from backend.app.services.privacy import redact_text
from agents.graph import run_copilot


router = APIRouter()


@router.post("/copilot", response_model=CopilotResponse)
def copilot(req: CopilotRequest) -> CopilotResponse:
    """Handle a user request via the copilot.

    Parameters
    ----------
    req: CopilotRequest
        The inbound request containing the user's message and session ID.

    Returns
    -------
    CopilotResponse
        The reply from the agent along with a trace of operations.
    """
    # Mask identifiers for privacy
    redaction = redact_text(req.message)

    reply, trace = run_copilot(message=redaction.redacted_text, session_id=req.session_id)
    if redaction.redactions:
        trace = [f"privacy:redacted={redaction.redactions}"] + trace

    return CopilotResponse(session_id=req.session_id, reply=reply, trace=trace)