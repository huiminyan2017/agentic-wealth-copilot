"""Spending service for CRUD operations on spending records.

Stores data as JSON files in data/parsed/<person>/spending/
"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional, Tuple

from ..schemas import (
    SpendingRecord,
    SpendingCreate,
    SpendingUpdate,
    RecurringSpending,
    RecurringSpendingCreate,
    RecurringSpendingUpdate,
)
from .paths import PARSED_DATA_DIR


def _generate_spending_id() -> str:
    """Generate a random unique ID for a spending record."""
    return str(uuid.uuid4())[:16]


def _get_spending_dir(person: str) -> Path:
    """Get the spending directory for a person, creating if needed."""
    base = PARSED_DATA_DIR / person / "spending"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _get_spending_file(person: str) -> Path:
    """Get the one-time spending JSON file path."""
    return _get_spending_dir(person) / "spending.json"


def _get_recurring_file(person: str) -> Path:
    """Get the recurring spending JSON file path."""
    return _get_spending_dir(person) / "recurring.json"


def _load_spending(person: str) -> List[dict]:
    """Load all one-time spending records for a person."""
    path = _get_spending_file(person)
    if not path.exists():
        return []
    with open(path, "r") as f:
        return json.load(f)


def _save_spending(person: str, records: List[dict]) -> None:
    """Save all one-time spending records for a person."""
    path = _get_spending_file(person)
    with open(path, "w") as f:
        json.dump(records, f, indent=2, default=str)


def _load_recurring(person: str) -> List[dict]:
    """Load all recurring spending records for a person."""
    path = _get_recurring_file(person)
    if not path.exists():
        return []
    with open(path, "r") as f:
        return json.load(f)


def _save_recurring(person: str, records: List[dict]) -> None:
    """Save all recurring spending records for a person."""
    path = _get_recurring_file(person)
    with open(path, "w") as f:
        json.dump(records, f, indent=2, default=str)


# ============================================================================
# One-time Spending CRUD
# ============================================================================

def list_spending(person: str, start_date: Optional[date] = None, end_date: Optional[date] = None) -> List[SpendingRecord]:
    """List all spending records, optionally filtered by date range."""
    records = _load_spending(person)
    results = []
    
    for r in records:
        # Parse date string back to date object
        rec_date = date.fromisoformat(r["date"]) if isinstance(r["date"], str) else r["date"]
        
        # Apply date filters
        if start_date and rec_date < start_date:
            continue
        if end_date and rec_date > end_date:
            continue
        
        # Convert to SpendingRecord
        r["date"] = rec_date
        results.append(SpendingRecord(**r))
    
    # Sort by date descending (most recent first)
    results.sort(key=lambda x: x.date, reverse=True)
    return results


def get_spending(person: str, spending_id: str) -> Optional[SpendingRecord]:
    """Get a single spending record by ID."""
    records = _load_spending(person)
    for r in records:
        if r["id"] == spending_id:
            r["date"] = date.fromisoformat(r["date"]) if isinstance(r["date"], str) else r["date"]
            return SpendingRecord(**r)
    return None


def create_spending(person: str, data: SpendingCreate) -> SpendingRecord:
    """Create a new spending record with a unique ID."""
    records = _load_spending(person)
    
    # Generate random unique ID
    record_id = _generate_spending_id()
    
    new_record = SpendingRecord(
        id=record_id,
        date=data.date,
        what=data.what,
        amount=data.amount,
        quantity=data.quantity,
        merchant=data.merchant,
        description=data.description,
        source=data.source,
        receipt_path=data.receipt_path,
        created_at=datetime.now().isoformat(),
    )
    
    records.append(new_record.model_dump())
    _save_spending(person, records)
    
    return new_record


def create_spending_batch(person: str, items: List[SpendingCreate]) -> List[SpendingRecord]:
    """Create multiple spending records at once (e.g., from receipt parsing).
    
    Args:
        person: Person name
        items: List of spending data to create
    
    Returns:
        List of created records
    """
    records = _load_spending(person)
    created = []
    
    for data in items:
        # Generate random unique ID
        record_id = _generate_spending_id()
        
        new_record = SpendingRecord(
            id=record_id,
            date=data.date,
            what=data.what,
            amount=data.amount,
            quantity=data.quantity,
            merchant=data.merchant,
            description=data.description,
            source=data.source,
            receipt_path=data.receipt_path,
            created_at=datetime.now().isoformat(),
        )
        records.append(new_record.model_dump())
        created.append(new_record)
    
    if created:
        _save_spending(person, records)
    
    return created


def detect_suspected_duplicates(person: str) -> List[List[SpendingRecord]]:
    """Detect suspected duplicate spending records.
    
    Returns groups of records that may be duplicates based on:
    - Same date
    - Same amount
    - Similar merchant (case-insensitive)
    
    Returns:
        List of groups, where each group is a list of potentially duplicate records
    """
    records = list_spending(person)
    
    # Group by (date, amount, normalized_merchant)
    from collections import defaultdict
    groups = defaultdict(list)
    
    for rec in records:
        # Normalize merchant for grouping
        merchant_key = (rec.merchant or "").lower().strip()
        # Remove common suffixes for matching
        for suffix in [" wholesale", " supercenter", " store", " inc", " llc", " corp"]:
            if merchant_key.endswith(suffix):
                merchant_key = merchant_key[:-len(suffix)]
        
        key = (rec.date, rec.amount, merchant_key)
        groups[key].append(rec)
    
    # Return only groups with more than one record (potential duplicates)
    duplicates = [group for group in groups.values() if len(group) > 1]
    
    # Sort groups by date (most recent first)
    duplicates.sort(key=lambda g: g[0].date, reverse=True)
    
    return duplicates


def update_spending(person: str, spending_id: str, data: SpendingUpdate) -> Optional[SpendingRecord]:
    """Update an existing spending record."""
    records = _load_spending(person)
    
    for i, r in enumerate(records):
        if r["id"] == spending_id:
            # Update only provided fields
            if data.date is not None:
                r["date"] = data.date.isoformat()
            if data.what is not None:
                r["what"] = data.what
            if data.amount is not None:
                r["amount"] = data.amount
            if data.quantity is not None:
                r["quantity"] = data.quantity
            if data.merchant is not None:
                r["merchant"] = data.merchant
            if data.description is not None:
                r["description"] = data.description
            
            records[i] = r
            _save_spending(person, records)
            
            r["date"] = date.fromisoformat(r["date"]) if isinstance(r["date"], str) else r["date"]
            return SpendingRecord(**r)
    
    return None


def delete_spending(person: str, spending_id: str) -> bool:
    """Delete a spending record by ID."""
    records = _load_spending(person)
    original_len = len(records)
    
    records = [r for r in records if r["id"] != spending_id]
    
    if len(records) < original_len:
        _save_spending(person, records)
        return True
    return False


# ============================================================================
# Recurring Spending CRUD
# ============================================================================

def list_recurring(person: str, active_only: bool = False) -> List[RecurringSpending]:
    """List all recurring spending entries."""
    records = _load_recurring(person)
    results = []
    
    for r in records:
        # Parse dates
        r["start_date"] = date.fromisoformat(r["start_date"]) if isinstance(r["start_date"], str) else r["start_date"]
        if r.get("end_date"):
            r["end_date"] = date.fromisoformat(r["end_date"]) if isinstance(r["end_date"], str) else r["end_date"]
        
        rec = RecurringSpending(**r)
        
        if active_only and not rec.is_active:
            continue
        
        results.append(rec)
    
    # Sort by amount descending
    results.sort(key=lambda x: x.amount, reverse=True)
    return results


def get_recurring(person: str, recurring_id: str) -> Optional[RecurringSpending]:
    """Get a single recurring spending entry by ID."""
    records = _load_recurring(person)
    for r in records:
        if r["id"] == recurring_id:
            r["start_date"] = date.fromisoformat(r["start_date"]) if isinstance(r["start_date"], str) else r["start_date"]
            if r.get("end_date"):
                r["end_date"] = date.fromisoformat(r["end_date"]) if isinstance(r["end_date"], str) else r["end_date"]
            return RecurringSpending(**r)
    return None


def create_recurring(person: str, data: RecurringSpendingCreate) -> RecurringSpending:
    """Create a new recurring spending entry."""
    records = _load_recurring(person)
    
    new_record = RecurringSpending(
        id=str(uuid.uuid4()),
        what=data.what,
        amount=data.amount,
        description=data.description,
        frequency=data.frequency,
        start_date=data.start_date,
        end_date=data.end_date,
        is_active=True,
        created_at=datetime.now().isoformat(),
    )
    
    records.append(new_record.model_dump())
    _save_recurring(person, records)
    
    return new_record


def update_recurring(person: str, recurring_id: str, data: RecurringSpendingUpdate) -> Optional[RecurringSpending]:
    """Update an existing recurring spending entry."""
    records = _load_recurring(person)
    
    for i, r in enumerate(records):
        if r["id"] == recurring_id:
            if data.what is not None:
                r["what"] = data.what
            if data.amount is not None:
                r["amount"] = data.amount
            if data.description is not None:
                r["description"] = data.description
            if data.frequency is not None:
                r["frequency"] = data.frequency
            if data.start_date is not None:
                r["start_date"] = data.start_date.isoformat()
            if data.end_date is not None:
                r["end_date"] = data.end_date.isoformat()
            if data.is_active is not None:
                r["is_active"] = data.is_active
            
            records[i] = r
            _save_recurring(person, records)
            
            r["start_date"] = date.fromisoformat(r["start_date"]) if isinstance(r["start_date"], str) else r["start_date"]
            if r.get("end_date"):
                r["end_date"] = date.fromisoformat(r["end_date"]) if isinstance(r["end_date"], str) else r["end_date"]
            return RecurringSpending(**r)
    
    return None


def delete_recurring(person: str, recurring_id: str) -> bool:
    """Delete a recurring spending entry by ID."""
    records = _load_recurring(person)
    original_len = len(records)
    
    records = [r for r in records if r["id"] != recurring_id]
    
    if len(records) < original_len:
        _save_recurring(person, records)
        return True
    return False


# ============================================================================
# Analytics
# ============================================================================

def get_spending_summary(person: str, start_date: Optional[date] = None, end_date: Optional[date] = None) -> dict:
    """Get spending summary with totals by category."""
    records = list_spending(person, start_date, end_date)
    recurring = list_recurring(person, active_only=True)
    
    # Sum by category
    by_category: dict[str, float] = {}
    for r in records:
        by_category[r.what] = by_category.get(r.what, 0) + r.amount
    
    # Calculate monthly recurring total
    monthly_recurring = 0.0
    freq_multipliers = {
        "daily": 30,
        "weekly": 4.33,
        "biweekly": 2.17,
        "monthly": 1,
        "quarterly": 0.33,
        "yearly": 0.083,
    }
    for r in recurring:
        multiplier = freq_multipliers.get(r.frequency, 1)
        monthly_recurring += r.amount * multiplier
    
    return {
        "total_one_time": sum(r.amount for r in records),
        "total_records": len(records),
        "by_category": by_category,
        "monthly_recurring": round(monthly_recurring, 2),
        "recurring_count": len(recurring),
    }
