"""Client wrapper for calling the backend API.

This module defines a simple synchronous wrapper around the FastAPI
backend's copilot endpoint.  It uses ``httpx`` under the hood and
respects environment variables defined in ``.env`` for the backend
host and port.  If no environment variables are set, it falls back to
localhost defaults.
"""

from __future__ import annotations

import os
import httpx


# Determine backend host and port from environment variables.  These
# default to localhost and the standard development port when not
# specified.
# BACKEND_HOST = os.getenv("BACKEND_HOST", "127.0.0.1")
# BACKEND_PORT = int(os.getenv("BACKEND_PORT", "8000"))
# BASE_URL = f"http://{BACKEND_HOST}:{BACKEND_PORT}"


# def copilot(message: str, session_id: str = "default") -> dict:
#     """Send a message to the copilot and return the JSON response.

#     Args:
#         message: The user's chat message.
#         session_id: A unique identifier for the conversation.

#     Returns:
#         A dictionary parsed from the JSON response of the backend.

#     Raises:
#         httpx.HTTPError: If the request fails or returns a non‑200 response.
#     """
#     payload = {"message": message, "session_id": session_id}
#     with httpx.Client(timeout=30) as client:
#         resp = client.post(f"{BASE_URL}/api/copilot", json=payload)
#         resp.raise_for_status()
#         return resp.json()

BACKEND_HOST = os.getenv("BACKEND_HOST", "127.0.0.1")
BACKEND_PORT = int(os.getenv("BACKEND_PORT", "8000"))
BASE = f"http://{BACKEND_HOST}:{BACKEND_PORT}"

def request_json(method: str, path: str, json_body=None) -> dict:
    with httpx.Client(timeout=600) as client:
        r = client.request(method, f"{BASE}{path}", json=json_body)
        r.raise_for_status()
        return r.json()