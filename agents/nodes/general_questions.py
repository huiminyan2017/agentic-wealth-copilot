"""General financial questions node — open-ended personal finance Q&A."""

from __future__ import annotations

from agents.state import CopilotState
from agents import llm
from agents.llm import config_error_reply


_SYSTEM_PROMPT = """You are a helpful personal financial advisor assistant.
You help users understand their personal finances including income, taxes, wealth, and investing.
Answer concisely and helpfully. If the user's question is outside personal finance, gently redirect.
If you don't know something specific about the user's finances, say so and suggest what data they could upload."""

_FALLBACK_MESSAGE = (
    "I can help you with:\n"
    "- **Income & Tax**: paystub analysis, W-2 review, withholding, tax optimisation\n"
    "- **Wealth**: net worth, property, savings, retirement progress\n"
    "- **Investing**: watchlist, stock alerts, portfolio rules\n\n"
    "Try asking something like: *\"What are my tax optimisation opportunities?\"* "
    "or *\"What is my net worth?\"*"
)


def general_node(state: CopilotState) -> CopilotState:
    state.reply = llm.chat([
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user",   "content": state.user_message},
    ]) or _FALLBACK_MESSAGE
    state.trace.append("general:ok")
    return state
