"""Income and tax node — runs analysis and uses LLM to answer the user's specific question."""

from __future__ import annotations

from agents.state import CopilotState
from agents.income_analysis import run_income_analysis
from agents import llm
from agents.llm import config_error_reply


def income_tax_node(state: CopilotState) -> CopilotState:
    person = state.person
    if not person:
        state.reply = "I don't know which person to analyse. Please mention a name (e.g. 'analyse Huimin's income')."
        state.trace.append("income_tax:error:no_person")
        return state

    try:
        result = run_income_analysis(person)
        report = result["report"]
        state.trace.extend(result["trace"])
        state.notes.append(f"income_tax:analysis_complete:{len(result['insights'])} insights")
    except Exception as e:
        state.reply = f"❌ Income analysis failed: {e}\n\nPlease ensure you have uploaded paystub or W-2 documents."
        state.trace.append(f"income_tax:error:{e}")
        return state

    # Use LLM to answer the user's specific question using the full analysis as context
    llm_reply = llm.chat([
        {
            "role": "system",
            "content": (
                "You are a helpful personal financial advisor. "
                "You have just run a full income and tax analysis for the user. "
                "Use the analysis report below to answer the user's specific question "
                "concisely and conversationally. Include relevant numbers and insights. "
                "If the question is broad (e.g. 'analyze my income'), return the full report."
            ),
        },
        {
            "role": "user",
            "content": (
                f"User question: {state.user_message}\n\n"
                f"Full analysis report:\n{report}"
            ),
        },
    ])

    state.reply = llm_reply if llm_reply else config_error_reply()
    return state
