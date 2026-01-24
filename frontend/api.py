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

BACKEND_HOST = os.getenv("BACKEND_HOST", "127.0.0.1")
BACKEND_PORT = int(os.getenv("BACKEND_PORT", "8000"))
BASE = f"http://{BACKEND_HOST}:{BACKEND_PORT}"

def request_json(method: str, path: str, json_body=None) -> dict:
    """Send a JSON request to the backend and return the parsed response.

    Opens a short-lived httpx client for each call (no persistent connection
    pool needed since Streamlit pages make infrequent, user-triggered calls).
    The 600 s timeout is intentionally generous to accommodate LangGraph agent
    runs, which can take 20-30 s for multi-step analysis.

    Args:
        method:    HTTP verb — "GET", "POST", "PUT", or "DELETE".
        path:      Endpoint path including any query string,
                   e.g. "/api/spending/summary?person=Huimin&start_date=2018-01-01".
                   Prepended with BASE (http://127.0.0.1:8000) automatically.
        json_body: Optional dict serialised as the request body.
                   Ignored for GET/DELETE requests by the server.

    Returns:
        Parsed JSON response as a plain dict.

    Raises:
        httpx.HTTPStatusError: if the server returns 4xx or 5xx.
        httpx.ConnectError:    if the backend is not running.
    """
    with httpx.Client(timeout=600) as client:
        r = client.request(method, f"{BASE}{path}", json=json_body)
        r.raise_for_status()
        return r.json()


def request_upload(path: str, file, data: dict = None) -> dict:
    """Upload a file to the backend API.
    
    Args:
        path: API endpoint path (e.g., "/api/spending/parse-receipt")
        file: File object (from st.file_uploader)
        data: Additional form data to send
    
    Returns:
        JSON response from the API
    """
    with httpx.Client(timeout=120) as client:
        files = {"receipt": (file.name, file.getvalue(), file.type or "image/jpeg")}
        r = client.post(f"{BASE}{path}", files=files, data=data or {})
        r.raise_for_status()
        return r.json()