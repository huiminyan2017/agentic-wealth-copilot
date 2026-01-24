"""Pydantic models for API input and output.

These models define the shapes of data sent to and returned from the FastAPI
endpoints.  They are deliberately simple for the initial scaffold but can be
expanded as additional features are implemented.
"""

from __future__ import annotations

from datetime import date
from pydantic import BaseModel, Field
from typing import Optional, List, Dict


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
    """Pydantic model representing the key fields of a W-2 form.

    Each attribute corresponds to a box on the IRS Form W-2.  Some
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
    
    # Box 12 codes with meaningful names
    box12_401k_pretax: Optional[float] = Field(None, description="Box 12 Code D: 401(k) elective deferrals (pre-tax)")
    box12_hsa: Optional[float] = Field(None, description="Box 12 Code W: HSA employer contributions (pre-tax)")
    box12_roth_401k: Optional[float] = Field(None, description="Box 12 Code AA: Roth 401(k) contributions (after-tax)")
    box12_gtl: Optional[float] = Field(None, description="Box 12 Code C: Taxable group-term life insurance over $50k")

    missing_fields: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    extracted_text_path: Optional[str] = None
    source_pdf_relpath: Optional[str] = None

    notes: Optional[str] = None


# ============================================================================
# PaystubRecordV2 - Structured format with nested value/details
# ============================================================================

class GrossDetails(BaseModel):
    """Gross pay value (no detailed breakdown typically)."""
    value: Optional[float] = None
    details: Dict[str, float] = Field(default_factory=dict)


class PretaxDeductionsDetails(BaseModel):
    """Pre-tax deductions breakdown: 401k + HSA EE."""
    value: Optional[float] = None
    details: Dict[str, float] = Field(default_factory=dict)
    # Expected keys in details: "401k", "hsa_ee"


class TaxesDetails(BaseModel):
    """Tax withholdings breakdown."""
    value: Optional[float] = None
    details: Dict[str, float] = Field(default_factory=dict)
    # Expected keys in details: "federal", "ss", "medicare", "state"


class AftertaxDeductionsDetails(BaseModel):
    """After-tax deductions breakdown."""
    value: Optional[float] = None
    details: Dict[str, float] = Field(default_factory=dict)
    # Expected keys in details: "401k", "401k-roth", "espp", "espp_refund", "dcfsa", "lpfsa", "add"


class NetPayDetails(BaseModel):
    """Net pay (take-home) value."""
    value: Optional[float] = None


class StockPayDetails(BaseModel):
    """Stock award details: income offset minus tax offset."""
    value: Optional[float] = None  # income - tax
    details: Dict[str, float] = Field(default_factory=dict)
    # Expected keys in details: "income", "tax"


class ValidationDetails(BaseModel):
    """Validation result with detailed diffs."""
    net_pay_diff: Optional[float] = None  # gross - net - stock_pay - pretax - taxes - aftertax ≈ 0
    tax_sum_diff: Optional[float] = None  # taxes.value - sum(taxes.details) ≈ 0
    pretax_sum_diff: Optional[float] = None  # pretax.value - sum(pretax.details) ≈ 0
    aftertax_sum_diff: Optional[float] = None  # aftertax.value - sum(aftertax.details) ≈ 0


class YTDDetails(BaseModel):
    """Year-to-date summary values."""
    gross: Optional[float] = None
    net_pay: Optional[float] = None
    federal_tax: Optional[float] = None
    state_tax: Optional[float] = None
    ss_tax: Optional[float] = None
    medicare_tax: Optional[float] = None


class PaystubRecordV2(BaseModel):
    """
    Paystub record with structured nested format.
    
    Format:
    {
      "gross": {"value": float, "details": {}},
      "pretax_deductions": {"value": float, "details": {"401k": float, "hsa_ee": float}},
      "taxes": {"value": float, "details": {"federal": float, "ss": float, "medicare": float, "state": float}},
      "aftertax_deductions": {"value": float, "details": {"401k": float, "401k-roth": float, "espp": float, "dcfsa": float, "lpfsa": float, "add": float}},
      "net_pay": {"value": float},
      "stock_pay": {"value": float, "details": {"income": float, "tax": float}},
      "validation": {"value": float}
    }
    
    Validation formula: gross - net_pay - pretax_deductions - taxes - aftertax_deductions = ~0
    """
    
    pay_date: Optional[date] = Field(None, description="Date of the pay period")
    employer_name: str = Field(..., description="Name of the employer")
    
    gross: GrossDetails = Field(default_factory=GrossDetails)
    pretax_deductions: PretaxDeductionsDetails = Field(default_factory=PretaxDeductionsDetails)
    taxes: TaxesDetails = Field(default_factory=TaxesDetails)
    aftertax_deductions: AftertaxDeductionsDetails = Field(default_factory=AftertaxDeductionsDetails)
    net_pay: NetPayDetails = Field(default_factory=NetPayDetails)
    stock_pay: StockPayDetails = Field(default_factory=StockPayDetails)
    validation: ValidationDetails = Field(default_factory=ValidationDetails)
    
    # YTD summary
    ytd: Optional[YTDDetails] = None
    
    # Raw extracted values for debugging (renamed from _raw to raw_values)
    raw_values: Dict[str, Optional[float]] = Field(default_factory=dict)
    
    # Metadata
    warnings: List[str] = Field(default_factory=list)
    source_pdf: Optional[str] = None
    parser: str = Field(default="unknown")
    
    model_config = {"populate_by_name": True}


# ============================================================================
# Spending Module Schemas
# ============================================================================

from datetime import date as date_type  # Import with alias for Pydantic compatibility


class SpendingRecord(BaseModel):
    """A single spending transaction."""
    
    id: str = Field(..., description="Unique identifier (hash of key fields for dedup)")
    date: date_type = Field(..., description="Transaction date")
    what: str = Field(..., description="Category or item name (e.g., 'Groceries', 'Gas')")
    amount: float = Field(..., description="Amount (positive for spending, negative for refunds)")
    quantity: int = Field(default=1, description="Quantity of items")
    merchant: Optional[str] = Field(None, description="Store/merchant name (e.g., 'Costco', 'Amazon')")
    description: Optional[str] = Field(None, description="Additional details or notes")
    source: str = Field(default="manual", description="How this was added: 'manual', 'receipt', 'import'")
    receipt_path: Optional[str] = Field(None, description="Path to receipt image if uploaded")
    created_at: Optional[str] = Field(None, description="ISO timestamp when record was created")


class RecurringSpending(BaseModel):
    """A recurring/periodic spending entry (e.g., subscriptions, rent)."""
    
    id: str = Field(..., description="Unique identifier (UUID)")
    what: str = Field(..., description="Category or item name")
    amount: float = Field(..., description="Amount per occurrence")
    description: Optional[str] = Field(None, description="Additional details")
    frequency: str = Field(..., description="Frequency: 'daily', 'weekly', 'biweekly', 'monthly', 'quarterly', 'yearly'")
    start_date: date_type = Field(..., description="When this recurring spend started")
    end_date: Optional[date_type] = Field(None, description="When it ends (None = ongoing)")
    is_active: bool = Field(default=True, description="Whether this recurring spend is active")
    created_at: Optional[str] = Field(None, description="ISO timestamp when record was created")


class SpendingCreate(BaseModel):
    """Request to create a new spending record."""
    
    date: date_type
    what: str
    amount: float
    quantity: int = 1
    merchant: Optional[str] = None
    description: Optional[str] = None
    source: str = "manual"
    receipt_path: Optional[str] = None


class SpendingUpdate(BaseModel):
    """Request to update an existing spending record."""
    
    date: Optional[date_type] = None
    what: Optional[str] = None
    amount: Optional[float] = None
    quantity: Optional[int] = None
    merchant: Optional[str] = None
    description: Optional[str] = None


class RecurringSpendingCreate(BaseModel):
    """Request to create a recurring spending entry."""
    
    what: str
    amount: float
    description: Optional[str] = None
    frequency: str
    start_date: date_type
    end_date: Optional[date_type] = None


class RecurringSpendingUpdate(BaseModel):
    """Request to update a recurring spending entry."""
    
    what: Optional[str] = None
    amount: Optional[float] = None
    description: Optional[str] = None
    frequency: Optional[str] = None
    start_date: Optional[date_type] = None
    end_date: Optional[date_type] = None
    is_active: Optional[bool] = None


class ReceiptParseResult(BaseModel):
    """Result of parsing a receipt image."""
    
    items: List[SpendingCreate] = Field(default_factory=list, description="Extracted spending items")
    extracted_date: Optional[date_type] = Field(None, description="Date extracted from receipt (even if all items filtered)")
    raw_text: Optional[str] = Field(None, description="Raw OCR text for debugging")
    confidence: Optional[float] = Field(None, description="Confidence score 0-1")
    warnings: List[str] = Field(default_factory=list, description="Any parsing warnings")


# Required for Pydantic v2 when using Optional/forward refs
PaystubRecordV2.model_rebuild()
W2Record.model_rebuild()
SpendingRecord.model_rebuild()
RecurringSpending.model_rebuild()
SpendingCreate.model_rebuild()
RecurringSpendingCreate.model_rebuild()
ReceiptParseResult.model_rebuild()