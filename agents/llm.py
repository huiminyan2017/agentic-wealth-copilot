"""Shared LLM client for the agents package.

Wraps Azure OpenAI using the same settings as the rest of the backend.
Falls back gracefully (returns None) if credentials are not configured,
so nodes can degrade to deterministic logic rather than crash.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Exported so the frontend can detect config errors without string-matching a private constant
LLM_CONFIG_ERROR_PREFIX = "LLM_CONFIG_ERROR"
_LLM_CONFIG_ERROR_PREFIX = LLM_CONFIG_ERROR_PREFIX  # backward-compat alias

# ── client factory (lazy, cached) ─────────────────────────────────────────────

_client = None
_last_error: str | None = None


def _get_client():
    global _client, _last_error
    if _client is not None:
        return _client
    try:
        from openai import AzureOpenAI
        from backend.app.settings import settings
        if not settings.azure_openai_endpoint or not settings.azure_openai_api_key:
            _last_error = "Azure OpenAI credentials are not configured. Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY in your .env file."
            return None
        _client = AzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
        )
        return _client
    except Exception as e:
        _last_error = f"Failed to initialise Azure OpenAI client: {e}"
        logger.warning(_last_error)
        return None


def _deployment() -> str:
    from backend.app.settings import settings
    return settings.azure_openai_deployment


# ── public helpers ─────────────────────────────────────────────────────────────

def chat(messages: list[dict], temperature: float = 0.2, max_tokens: int = 1500) -> str | None:
    """Send a chat completion request. Returns the reply text or None on failure."""
    client = _get_client()
    if client is None:
        return None
    try:
        resp = client.chat.completions.create(
            model=_deployment(),
            messages=messages,
            temperature=temperature,
            max_completion_tokens=max_tokens,
        )
        return resp.choices[0].message.content
    except Exception as e:
        global _last_error
        _last_error = str(e)
        logger.warning(f"LLM chat failed: {e}")
        return None


def chat_json(messages: list[dict], temperature: float = 0.1) -> dict | None:
    """Like chat() but parses the response as JSON. Returns None on failure."""
    client = _get_client()
    if client is None:
        return None
    try:
        resp = client.chat.completions.create(
            model=_deployment(),
            messages=messages,
            temperature=temperature,
            max_completion_tokens=500,
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content)
    except Exception as e:
        logger.warning(f"LLM chat_json failed: {e}")
        return None


def config_error_reply() -> str:
    """Return a user-facing error string that the frontend detects and renders as st.error()."""
    err = _last_error or "Unknown error"
    return (
        f"{_LLM_CONFIG_ERROR_PREFIX}: {err}\n\n"
        "**To fix:** update `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, and "
        "`AZURE_OPENAI_DEPLOYMENT` in your `.env` file, then restart the backend."
    )


