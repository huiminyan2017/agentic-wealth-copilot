# Wealth & Planning Module

> **Status:** Implemented ✅

This module tracks personal wealth across multiple asset types and provides goal-setting with progress tracking.

## Features

### Per-Person Tracking
- Select from available people (auto-detected from `data/raw/` directories)
- Each person has separate wealth data stored in `data/parsed/wealth_data_{person}.json`

### Asset Tracking

| Asset Type | Description | Notes |
|------------|-------------|-------|
| 💵 Cash & Savings | Bank accounts, savings, money market funds | Full ownership |
| 🏠 Primary Property | Primary residence value | Supports shared ownership (value ÷ owners) |
| 🏘️ Investment Properties | Rental properties, land, real estate investments | Supports shared ownership |
| 📈 Stocks & Investments | Stocks, ETFs, mutual funds in taxable accounts | Full ownership |
| 🏦 401(k) / Retirement | 401(k), IRA, Roth IRA, other retirement accounts | Full ownership |

### Ownership Splitting
For properties (primary and investment), users can specify:
- **Total Value**: Full market value of the property
- **Number of Owners**: How many people share ownership
- **Your Share**: Automatically calculated as Total ÷ Owners

This allows couples to track their individual wealth when jointly owning property.

### Wealth Calculations

| Metric | Formula | Purpose |
|--------|---------|---------|
| **Total Wealth** | Cash + Primary Property + Investment Properties + Stocks + 401(k) | Overall net worth |
| **Non-Retirement Wealth** | Cash + Investment Properties + Stocks | Wealth excluding 401(k) and primary home |

**Why exclude primary property from Non-Retirement Wealth?**
- Primary home is for living, not generating investment returns
- Cannot easily liquidate for retirement income
- Tracked separately for goal planning

### Financial Targets

| Target | Description |
|--------|-------------|
| 🎯 Target 401(k) Balance | Goal for retirement account balance |
| 🎯 Target Non-Retirement Wealth | Goal for investable wealth (excludes 401k and primary home) |

### Progress Tracking
- Visual progress bars for each target
- Percentage completion displayed
- Shows remaining amount to reach goal
- "Goal reached! 🎉" celebration when targets are met

### Display Features
- Compact number formatting ($1.2M, $350K) for readability
- Summary metrics in card layout
- Info box highlighting investable wealth

## Data Storage

```json
// data/parsed/{person}/wealth.json
{
  "current": {
    "cash": 10000.0,
    "primary_property_total": 1200000.0,
    "primary_owners": 2,
    "primary_property": 600000.0,
    "investment_properties_total": 0.0,
    "investment_owners": 1,
    "investment_properties": 0.0,
    "stock_value": 120000.0,
    "retirement_401k": 350000.0
  },
  "targets": {
    "target_401k": 1000000.0,
    "target_non_retirement": 1000000.0
  },
  "last_updated": "2026-02-01"
}
```

## UI Location

**Sidebar:** Wealth & Planning (page 2)

## Future Enhancements

- [ ] Track liabilities (mortgage, loans, credit cards)
- [ ] Historical wealth tracking over time
- [ ] Wealth trend charts
- [ ] Concentration risk analysis
- [ ] Net worth calculation (assets - liabilities)
