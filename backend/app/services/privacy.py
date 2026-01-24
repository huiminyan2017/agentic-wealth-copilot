"""Simple privacy redaction helpers.

This module provides functions to redact obvious identifiers such as Social
Security numbers (SSN) and Employer Identification Numbers (EIN) from text.
The redaction functions return the redacted text as well as metadata about
what types of identifiers were removed.  You can extend this module to
support additional patterns (e.g. names, addresses) as needed.
"""

from dataclasses import dataclass
import re
from typing import List


_SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_EIN_PATTERN = re.compile(r"\b\d{2}-\d{7}\b")


@dataclass
class RedactionResult:
    """Result of a redaction operation."""

    redacted_text: str
    redactions: List[str]


def redact_text(text: str) -> RedactionResult:
    """Redact known identifiers in ``text``.

    Currently this function masks SSNs and EINs with placeholder patterns.  It
    returns both the redacted text and a list of the redaction types
    performed.
    """
    redactions: List[str] = []
    redacted = text

    if _SSN_PATTERN.search(redacted):
        redactions.append("ssn")
        redacted = _SSN_PATTERN.sub("XXX-XX-XXXX", redacted)

    if _EIN_PATTERN.search(redacted):
        redactions.append("ein")
        redacted = _EIN_PATTERN.sub("XX-XXXXXXX", redacted)

    return RedactionResult(redacted_text=redacted, redactions=redactions)