"""Pydantic models for API input and output.

These models define the shapes of data sent to and returned from the FastAPI
endpoints.  They are deliberately simple for the initial scaffold but can be
expanded as additional features are implemented.
"""

from __future__ import annotations

from datetime import date
from pydantic import BaseModel, Field
from typing import Optional, List


class CopilotRequest(BaseModel):
    """Request payload for the copilot endpoint."""

    message: str = Field(..., description="User's message")
    session_id: str = Field(default="default", description="Unique session identifier")


class CopilotResponse(BaseModel):
    """Response payload from the copilot endpoint."""

    session_id: str = Field(..., description="Session identifier")
    reply: str = Field(..., description="Agent's reply")
    trace: List[str] = Field(default_factory=list, description="Trace of operations")


class HealthResponse(BaseModel):
    """Simple health check response."""

    status: str = Field(..., description="Health status (e.g. 'ok')")


class W2Record(BaseModel):
    """Pydantic model representing the key fields of a W‑2 form.

    Each attribute corresponds to a box on the IRS Form W‑2.  Some
    fields (such as state wages and state tax withheld) may not be
    present on all forms and are therefore optional.  The ``notes``
    field allows callers to attach contextual information such as
    sanitization details or extraction warnings.
    """

    year: int = Field(..., description="Tax year reported on the W-2")
    employer_name: str = Field(..., description="Name of the employer (sanitized)")

    wages: Optional[float] = None
    federal_tax_withheld: Optional[float] = None
    ss_wages: Optional[float] = None
    ss_tax_withheld: Optional[float] = None
    medicare_wages: Optional[float] = None
    medicare_tax_withheld: Optional[float] = None

    state_wages: Optional[float] = None
    state_tax_withheld: Optional[float] = None

    missing_fields: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    extracted_text_path: Optional[str] = None
    source_pdf_relpath: Optional[str] = None

    notes: Optional[str] = None


class PaystubRecord(BaseModel):
    """Pydantic model representing a single pay period and YTD figures.

    The paystub schema captures both per‑period and year‑to‑date totals.
    Deductions are split into pre‑tax and post‑tax to allow accurate
    computation of taxable wages.  The ``other_taxes`` field can be
    used for local, SDI or other miscellaneous taxes.  Optional
    ``notes`` may be used to record sanitisation or parsing caveats.
    """

    pay_date: date = Field(..., description="Date of the pay period")
    employer_name: str = Field(..., description="Name of the employer (sanitized)")

    gross_pay: Optional[float] = None
    pre_tax_deductions: Optional[float] = None
    post_tax_deductions: Optional[float] = None
    taxable_wages: Optional[float] = None

    federal_tax: Optional[float] = None
    ss_tax: Optional[float] = None
    medicare_tax: Optional[float] = None
    state_tax: Optional[float] = None
    other_taxes: Optional[float] = None

    net_pay: Optional[float] = None

    ytd_gross: Optional[float] = None
    ytd_taxable_wages: Optional[float] = None
    ytd_federal_tax: Optional[float] = None
    ytd_state_tax: Optional[float] = None
    ytd_ss_tax: Optional[float] = None
    ytd_medicare_tax: Optional[float] = None

    # quality + debug
    missing_fields: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    extracted_text_path: Optional[str] = None
    source_pdf_relpath: Optional[str] = None

    notes: Optional[str] = None

# Required for Pydantic v2 when using Optional/forward refs
PaystubRecord.model_rebuild()
W2Record.model_rebuild()