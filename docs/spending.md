# Spending Module

The Spending module tracks one-time transactions, recurring expenses, and parses receipt images. Data is stored per-person in `data/parsed/<person>/spending/`.

---

## Data Models

### SpendingRecord (one-time transaction)

```json
{
  "id": "a1b2c3d4e5f6g7h8",
  "date": "2026-01-15",
  "what": "Groceries",
  "amount": 87.50,
  "quantity": 1,
  "merchant": "Costco",
  "description": "Weekly groceries",
  "source": "manual",
  "receipt_path": null,
  "created_at": "2026-01-15T10:30:00Z"
}
```

**ID generation:** Deterministic hash of `(date, amount, merchant)` — duplicate submissions produce the same ID and are silently skipped.

**`source`** values: `"manual"` (entered by user), `"receipt"` (extracted from receipt image).

### RecurringSpending

```json
{
  "id": "d2e3f4g5h6i7j8k9",
  "what": "Internet",
  "amount": 79.99,
  "description": "Fiber internet subscription",
  "frequency": "monthly",
  "start_date": "2024-01-01",
  "end_date": null,
  "is_active": true,
  "created_at": "2024-01-01T00:00:00Z"
}
```

**`frequency`** values: `daily`, `weekly`, `biweekly`, `monthly`, `quarterly`, `yearly`

---

## Storage

```
data/parsed/<person>/spending/
├── spending.json     # list of SpendingRecord
└── recurring.json    # list of RecurringSpending
```

Both files are plain JSON arrays. Writes replace the entire file atomically.

---

## API Reference

All endpoints are prefixed with `/api`.

### One-Time Spending

| Method | Path | Description |
|---|---|---|
| `GET` | `/spending/list` | List transactions. Query params: `person`, `start_date`, `end_date` |
| `GET` | `/spending/{id}` | Get one record |
| `POST` | `/spending` | Create a record |
| `POST` | `/spending/batch` | Create multiple records at once |
| `PUT` | `/spending/{id}` | Update a record |
| `DELETE` | `/spending/{id}` | Delete a record |
| `GET` | `/spending/duplicates` | Return groups of suspected duplicates |
| `GET` | `/spending/summary` | Totals and category breakdown |

### Recurring Spending

| Method | Path | Description |
|---|---|---|
| `GET` | `/spending/recurring/list` | List entries. Returns `monthly_total` aggregate |
| `POST` | `/spending/recurring` | Create entry |
| `PUT` | `/spending/recurring/{id}` | Update entry |
| `DELETE` | `/spending/recurring/{id}` | Delete entry |

### Receipt Parsing

```
POST /api/spending/parse-receipt
Content-Type: multipart/form-data
  receipt: <image file>
  person: <name>
```

Returns a `ReceiptParseResult`:
```json
{
  "items": [
    {"date": "2026-01-15", "what": "Coffee", "amount": 5.50, "merchant": "Starbucks", "source": "receipt"}
  ],
  "extracted_date": "2026-01-15",
  "confidence": 0.93,
  "warnings": []
}
```

Items are returned for review — they are **not** automatically saved. The user confirms before the frontend calls `POST /spending/batch`.

Receipt parsing uses **Azure Document Intelligence** (`AZURE_DOC_INTELLIGENCE_*` env vars required).

---

## Duplicate Detection

`GET /api/spending/duplicates` groups records that share the same date and amount with a similar merchant name (fuzzy match). Each group is a list of `SpendingRecord` objects — the UI highlights them for the user to review and delete.

---

## UI

The **Spending** page (`frontend/pages/4_Spending.py`) has two tabs:

### Individual
- **One-Time Spending**: Add, edit, delete, date-filter transactions. Charts: by category, by day/week/month.
- **Recurring Spending**: Add/edit/delete recurring entries. Shows calculated monthly total.
- **Receipt Parsing**: Upload a receipt image, review extracted items, save with one click.
- **Duplicates**: Button to scan for and review suspected duplicate entries.

### Household Overview
Aggregates spending across all people in `data/parsed/`. Comparison charts by person and category.

---

## Service
**File:** `backend/app/services/spending.py`

Key functions:

```python
list_spending(person, start_date=None, end_date=None) -> list[SpendingRecord]
get_spending(person, spending_id) -> SpendingRecord | None
create_spending(person, data: SpendingCreate) -> SpendingRecord
update_spending(person, spending_id, data) -> SpendingRecord | None
delete_spending(person, spending_id) -> bool
detect_suspected_duplicates(person) -> list[list[SpendingRecord]]
get_spending_summary(person, start_date=None, end_date=None) -> dict
```

Recurring functions mirror the one-time set with `_recurring` suffix.
