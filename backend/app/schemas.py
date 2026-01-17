"""Pydantic models for API input and output.

These models define the shapes of data sent to and returned from the FastAPI
endpoints.  They are deliberately simple for the initial scaffold but can be
expanded as additional features are implemented.
"""

from __future__ import annotations

from typing import List
from datetime import date
from pydantic import BaseModel, Field


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

    year: int = Field(..., description="Tax year reported on the W‑2")
    employer_name: str = Field(..., description="Name of the employer (sanitized)")
    wages: float = Field(..., description="Box 1 – Wages, tips, other compensation")
    federal_tax_withheld: float = Field(..., description="Box 2 – Federal income tax withheld")
    ss_wages: float = Field(..., description="Box 3 – Social Security wages")
    ss_tax_withheld: float = Field(..., description="Box 4 – Social Security tax withheld")
    medicare_wages: float = Field(..., description="Box 5 – Medicare wages and tips")
    medicare_tax_withheld: float = Field(..., description="Box 6 – Medicare tax withheld")
    state_wages: float | None = Field(None, description="Box 16 – State wages, tips, etc.")
    state_tax_withheld: float | None = Field(None, description="Box 17 – State income tax")
    notes: str | None = Field(None, description="Additional contextual information")


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
    gross_pay: float = Field(..., description="Total earnings for the period")
    pre_tax_deductions: float = Field(..., description="Sum of pre‑tax deductions")
    post_tax_deductions: float = Field(..., description="Sum of post‑tax deductions")
    taxable_wages: float = Field(..., description="Wages subject to income tax after pre‑tax deductions")
    federal_tax: float = Field(..., description="Federal income tax withheld for the period")
    ss_tax: float = Field(..., description="Social Security tax withheld for the period")
    medicare_tax: float = Field(..., description="Medicare tax withheld for the period")
    state_tax: float = Field(..., description="State income tax withheld for the period")
    other_taxes: float = Field(..., description="Any other taxes (e.g. local, SDI)")
    net_pay: float = Field(..., description="Take‑home pay after all deductions and taxes")
    ytd_gross: float = Field(..., description="Year‑to‑date gross pay")
    ytd_taxable_wages: float = Field(..., description="Year‑to‑date taxable wages")
    ytd_federal_tax: float = Field(..., description="Year‑to‑date federal tax")
    ytd_state_tax: float = Field(..., description="Year‑to‑date state tax")
    ytd_ss_tax: float = Field(..., description="Year‑to‑date Social Security tax")
    ytd_medicare_tax: float = Field(..., description="Year‑to‑date Medicare tax")
    notes: str | None = Field(None, description="Additional contextual information")