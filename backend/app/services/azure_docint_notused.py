from __future__ import annotations

import os
from pathlib import Path

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential


def _get_env(name: str) -> str | None:
    v = os.getenv(name)
    return v.strip() if v and v.strip() else None


def is_configured() -> bool:
    return bool(_get_env("AZURE_DOCINT_ENDPOINT") and _get_env("AZURE_DOCINT_KEY"))


def get_client() -> DocumentIntelligenceClient:
    endpoint = _get_env("AZURE_DOCINT_ENDPOINT")
    key = _get_env("AZURE_DOCINT_KEY")
    if not endpoint or not key:
        raise RuntimeError("Azure Document Intelligence not configured. Set AZURE_DOCINT_ENDPOINT and AZURE_DOCINT_KEY.")
    return DocumentIntelligenceClient(endpoint=endpoint, credential=AzureKeyCredential(key))


def analyze_layout(pdf_path: Path):
    """
    Uses the layout model (tables + lines + paragraphs). Best for columnar paystubs.
    """
    client = get_client()
    with pdf_path.open("rb") as f:
        poller = client.begin_analyze_document(model_id="prebuilt-layout", body=f)
    return poller.result()