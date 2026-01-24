"""Spending API routes for CRUD operations and receipt parsing."""

from __future__ import annotations

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field

from backend.app.schemas import (
    SpendingRecord,
    SpendingCreate,
    SpendingUpdate,
    RecurringSpending,
    RecurringSpendingCreate,
    RecurringSpendingUpdate,
    ReceiptParseResult,
)
from backend.app.services.spending import (
    list_spending,
    get_spending,
    create_spending,
    create_spending_batch,
    update_spending,
    delete_spending,
    list_recurring,
    get_recurring,
    create_recurring,
    update_recurring,
    delete_recurring,
    get_spending_summary,
    detect_suspected_duplicates,
)
from backend.app.services.receipt_parser import parse_receipt_from_bytes


router = APIRouter()


# ============================================================================
# One-time Spending Endpoints
# ============================================================================

class SpendingListResponse(BaseModel):
    """Response for listing spending records."""
    items: List[SpendingRecord]
    total: int


@router.get("/spending/list", response_model=SpendingListResponse)
def api_list_spending(
    person: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> SpendingListResponse:
    """List all spending records for a person, optionally filtered by date range."""
    items = list_spending(person, start_date, end_date)
    return SpendingListResponse(items=items, total=len(items))


# NOTE: fixed-path GET routes must come before /spending/{spending_id} to avoid
# the catch-all swallowing them.

class DuplicatesResponse(BaseModel):
    """Response listing suspected duplicate groups."""
    duplicate_groups: List[List[SpendingRecord]]
    total_groups: int


@router.get("/spending/duplicates", response_model=DuplicatesResponse)
def api_detect_duplicates(person: str) -> DuplicatesResponse:
    """Detect suspected duplicate spending records."""
    groups = detect_suspected_duplicates(person)
    return DuplicatesResponse(duplicate_groups=groups, total_groups=len(groups))


class SpendingSummary(BaseModel):
    """Spending summary with totals and breakdowns."""
    total_one_time: float
    total_records: int
    by_category: dict
    monthly_recurring: float
    recurring_count: int


@router.get("/spending/summary", response_model=SpendingSummary)
def api_spending_summary(
    person: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> SpendingSummary:
    """Get spending summary with category breakdown."""
    summary = get_spending_summary(person, start_date, end_date)
    return SpendingSummary(**summary)


@router.get("/spending/{spending_id}", response_model=SpendingRecord)
def api_get_spending(person: str, spending_id: str) -> SpendingRecord:
    """Get a single spending record by ID."""
    record = get_spending(person, spending_id)
    if not record:
        raise HTTPException(status_code=404, detail="Spending record not found")
    return record


@router.post("/spending", response_model=SpendingRecord)
def api_create_spending(person: str, data: SpendingCreate) -> SpendingRecord:
    """Create a new spending record."""
    return create_spending(person, data)


class BatchSpendingCreate(BaseModel):
    """Request to create multiple spending records."""
    items: List[SpendingCreate]


class BatchSpendingResponse(BaseModel):
    """Response from batch spending creation."""
    created: List[SpendingRecord]


@router.post("/spending/batch", response_model=BatchSpendingResponse)
def api_create_spending_batch(person: str, data: BatchSpendingCreate) -> BatchSpendingResponse:
    """Create multiple spending records at once."""
    created = create_spending_batch(person, data.items)
    return BatchSpendingResponse(created=created)




@router.put("/spending/{spending_id}", response_model=SpendingRecord)
def api_update_spending(person: str, spending_id: str, data: SpendingUpdate) -> SpendingRecord:
    """Update an existing spending record."""
    record = update_spending(person, spending_id, data)
    if not record:
        raise HTTPException(status_code=404, detail="Spending record not found")
    return record


@router.delete("/spending/{spending_id}")
def api_delete_spending(person: str, spending_id: str) -> dict:
    """Delete a spending record."""
    success = delete_spending(person, spending_id)
    if not success:
        raise HTTPException(status_code=404, detail="Spending record not found")
    return {"deleted": True, "id": spending_id}


# ============================================================================
# Recurring Spending Endpoints
# ============================================================================

class RecurringListResponse(BaseModel):
    """Response for listing recurring spending entries."""
    items: List[RecurringSpending]
    total: int
    monthly_total: float


@router.get("/spending/recurring/list", response_model=RecurringListResponse)
def api_list_recurring(person: str, active_only: bool = False) -> RecurringListResponse:
    """List all recurring spending entries."""
    items = list_recurring(person, active_only)
    
    # Calculate monthly total
    freq_multipliers = {
        "daily": 30,
        "weekly": 4.33,
        "biweekly": 2.17,
        "monthly": 1,
        "quarterly": 0.33,
        "yearly": 0.083,
    }
    monthly = sum(r.amount * freq_multipliers.get(r.frequency, 1) for r in items if r.is_active)
    
    return RecurringListResponse(items=items, total=len(items), monthly_total=round(monthly, 2))


@router.get("/spending/recurring/{recurring_id}", response_model=RecurringSpending)
def api_get_recurring(person: str, recurring_id: str) -> RecurringSpending:
    """Get a single recurring spending entry by ID."""
    record = get_recurring(person, recurring_id)
    if not record:
        raise HTTPException(status_code=404, detail="Recurring spending not found")
    return record


@router.post("/spending/recurring", response_model=RecurringSpending)
def api_create_recurring(person: str, data: RecurringSpendingCreate) -> RecurringSpending:
    """Create a new recurring spending entry."""
    return create_recurring(person, data)


@router.put("/spending/recurring/{recurring_id}", response_model=RecurringSpending)
def api_update_recurring(person: str, recurring_id: str, data: RecurringSpendingUpdate) -> RecurringSpending:
    """Update an existing recurring spending entry."""
    record = update_recurring(person, recurring_id, data)
    if not record:
        raise HTTPException(status_code=404, detail="Recurring spending not found")
    return record


@router.delete("/spending/recurring/{recurring_id}")
def api_delete_recurring(person: str, recurring_id: str) -> dict:
    """Delete a recurring spending entry."""
    success = delete_recurring(person, recurring_id)
    if not success:
        raise HTTPException(status_code=404, detail="Recurring spending not found")
    return {"deleted": True, "id": recurring_id}


# ============================================================================
# Receipt Parsing Endpoint
# ============================================================================

@router.post("/spending/parse-receipt", response_model=ReceiptParseResult)
async def api_parse_receipt(
    person: str = Form(...),
    receipt: UploadFile = File(...),
    default_date: Optional[str] = Form(None),
) -> ReceiptParseResult:
    """Parse a receipt image and extract spending items.
    
    Returns extracted items that can be reviewed before saving.
    """
    # Read the uploaded file
    contents = await receipt.read()
    
    # Parse default_date if provided
    parsed_date = None
    if default_date:
        try:
            parsed_date = date.fromisoformat(default_date)
        except ValueError:
            pass
    
    # Parse the receipt
    result = parse_receipt_from_bytes(
        file_bytes=contents,
        filename=receipt.filename or "receipt.jpg",
        person=person,
        default_date=parsed_date,
    )
    
    return result


