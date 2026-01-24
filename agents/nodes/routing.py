"""Routing node — LLM intent classification with keyword fallback."""

from __future__ import annotations

from agents.state import CopilotState
from agents import llm
from agents.llm import config_error_reply


_ROUTING_PROMPT = """You are a financial assistant router. Classify the user's message into exactly one intent and extract context.

Intents:
- income_tax   : questions about paystubs, W-2s, withholding, salary, taxes, income trends
- wealth       : questions about net worth, assets, property, savings, investments, wealth comparison between people
- investing    : questions about buying/selling stocks, rebalancing, trading rules, portfolio thresholds
- general      : greetings, clarifications, questions about what the assistant can do, or anything else

Return JSON with these fields:
- intent: one of the four intents above
- people: list of person names explicitly mentioned (e.g. ["Huimin", "Bao"]), empty list if none
- sub_intent: one short sentence describing what specifically the user wants
- confidence: "high" | "medium" | "low"
"""


def _keyword_fallback(msg: str) -> str:
    m = msg.lower()
    if any(k in m for k in ["w2", "paystub", "withholding", "income", "salary", "tax"]):
        return "income_tax"
    if any(k in m for k in ["net worth", "wealth", "property", "mortgage", "savings",
                             "asset", "stock", "brokerage", "diff", "compare"]):
        return "wealth"
    if any(k in m for k in ["sell", "buy", "threshold", "trading", "rebalance"]):
        return "investing"
    return "general"


def routing_node(state: CopilotState) -> CopilotState:
    result = llm.chat_json([
        {"role": "system", "content": _ROUTING_PROMPT},
        {"role": "user",   "content": state.user_message},
    ])

    if result and "intent" in result:
        intent = result["intent"]
        people = result.get("people", [])
        sub    = result.get("sub_intent", "")
        conf   = result.get("confidence", "?")
        if people:
            state.notes.append(f"people:{','.join(people)}")
            state.person = people[0]
        state.sub_intent = [sub] if sub else []
        state.trace.append(f"routing:llm:intent={intent}:conf={conf}")
    else:
        # LLM unavailable — fall back to keyword matching instead of erroring
        intent = _keyword_fallback(state.user_message)
        state.trace.append(f"routing:llm_unavailable:keyword_fallback:intent={intent}")

    state.intent = intent
    return state
