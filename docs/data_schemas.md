# Data Schemas

This document defines the core data models used throughout Agentic Wealth Copilot.  Schemas are expressed in YAML‐like pseudocode for readability.  They will be implemented as Pydantic models in the backend.

## W2Record

Represents the key fields extracted from a W‑2 form.

```yaml
W2Record:
  year: int                   # Tax year
  employer_name: str          # Name of the employer (sanitized)
  wages: float                # Box 1 – Wages, tips, other compensation
  federal_tax_withheld: float # Box 2 – Federal income tax withheld
  ss_wages: float             # Box 3 – Social Security wages
  ss_tax_withheld: float      # Box 4 – Social Security tax withheld
  medicare_wages: float       # Box 5 – Medicare wages and tips
  medicare_tax_withheld: float# Box 6 – Medicare tax withheld
  state_wages: float          # Box 16 – State wages, tips, etc.
  state_tax_withheld: float   # Box 17 – State income tax
  notes: Optional[str]        # Additional contextual information
```

## PaystubRecord

Represents a single pay period from a paystub as well as year‑to‑date totals.

```yaml
PaystubRecord:
  pay_date: date              # Date of the pay period
  employer_name: str          # Name of the employer (sanitized)
  gross_pay: float            # Total earnings for the period
  pre_tax_deductions: float   # Sum of pre‑tax deductions (e.g. health insurance, 401(k))
  post_tax_deductions: float  # Sum of post‑tax deductions (e.g. Roth 401(k), after‑tax benefits)
  taxable_wages: float        # Wages subject to income tax after pre‑tax deductions
  federal_tax: float          # Federal income tax withheld for the period
  ss_tax: float               # Social Security tax withheld
  medicare_tax: float         # Medicare tax withheld
  state_tax: float            # State income tax withheld
  other_taxes: float          # Any other taxes (e.g. local, SDI)
  net_pay: float              # Take‑home pay after all deductions and taxes
  ytd_gross: float            # Year‑to‑date gross pay
  ytd_taxable_wages: float    # Year‑to‑date taxable wages
  ytd_federal_tax: float      # Year‑to‑date federal tax
  ytd_state_tax: float        # Year‑to‑date state tax
  ytd_ss_tax: float           # Year‑to‑date Social Security tax
  ytd_medicare_tax: float     # Year‑to‑date Medicare tax
  notes: Optional[str]        # Additional contextual information
```

## Asset

Represents an asset or liability in the net worth calculation.  The schema is flexible enough to accommodate many asset types.

```yaml
Asset:
  id: str                     # Unique identifier
  type: str                   # Asset type (cash, stock, bond, ETF, property, retirement, crypto, other)
  name: str                   # Human‑friendly name (e.g. "Checking Account", "MSFT")
  owner: str                  # Owner (user, spouse, joint, etc.)
  value: float                # Current estimated value
  cost_basis: float           # Original cost basis (for taxable assets)
  quantity: Optional[float]   # Quantity or shares (for securities)
  purchase_date: Optional[date]# Date of acquisition
  liquidity_score: int        # Scale from 1 (illiquid) to 5 (highly liquid)
  risk_score: int             # Scale from 1 (low risk) to 5 (high risk)
  category: Optional[str]     # Sub‑category (e.g. large‑cap, bond fund, rental)
  notes: Optional[str]        # Additional metadata
```

## TradingRule

Represents a user‑defined rule for conditional trading.

```yaml
TradingRule:
  id: str                     # Unique identifier
  asset_ticker: str           # Ticker symbol of the asset (e.g. "MSFT")
  condition: str              # Condition expression (e.g. "price >= 450")
  action: str                 # Action to perform (e.g. "sell 20%")
  fallback: Optional[str]     # Fallback action if the rule is cancelled (e.g. "buy back at 380")
  created_at: datetime        # Timestamp when the rule was created
  notes: Optional[str]        # Additional context
```

These schemas will be implemented as Pydantic models in `backend/app/schemas.py` and can be serialized to/from JSON for storage and API responses.