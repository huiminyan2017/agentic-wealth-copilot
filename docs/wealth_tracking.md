# Wealth & Net Worth Module

The Wealth & Net Worth Module aggregates all of your assets and liabilities to provide a comprehensive view of your financial position.  It supports real estate, cash, brokerage accounts, retirement accounts and any other assets you may own.

## Goals

* Define a flexible schema for recording assets and liabilities across categories (cash, stocks, ETFs, bonds, property, retirement accounts, crypto, etc.).
* Track the purchase price, cost basis, current value and ownership of each asset.
* Compute and display net worth, liquid net worth and invested net worth, both for you individually and for your family.
* Analyze trends over time: growth, drawdown, asset mix shifts and concentration risks.
* Provide alerts if net worth becomes overly concentrated in a single asset class or company.

## Key Concepts

| Concept             | Description |
|---------------------|-------------|
| **Asset**           | An item of value owned by you or your family.  Each asset has a type, value, cost basis, owner, liquidity score and other metadata. |
| **Liability**       | A debt or obligation (e.g. mortgage, credit card balance).  Liabilities reduce net worth. |
| **Net Worth**       | Total assets minus total liabilities. |
| **Liquid Net Worth**| Assets that can be converted to cash quickly (e.g. checking, savings, brokerage) minus liabilities. |
| **Invested Net Worth**| Value of assets held for investment purposes (e.g. stocks, bonds, retirement) excluding personal property. |

## Planned Components

* **AssetRegistry** – Stores all assets and liabilities and provides CRUD operations for adding, updating and removing entries.
* **PropertyAnalyzer** – Calculates current property value, mortgage balance, equity and appreciation using local data or third‑party APIs.
* **WealthAggregator** – Combines asset values and liabilities to produce net worth figures for individuals and for the household.
* **WealthTrendAnalyzer** – Computes year‑over‑year changes, asset allocation shifts and identifies concentration risks.

## Inputs & Outputs

* **Inputs:** Manual entry of asset and liability information; documents such as mortgage statements or brokerage account exports; configuration settings (e.g. ownership percentages).
* **Outputs:** Tables and charts summarizing net worth, asset allocation and trends; alerts about concentration or liquidity issues; insights for rebalancing.

## Open Questions

* How should we handle shared assets (e.g. jointly owned property) and apportion value to each owner?
* Should real estate valuations be updated manually or via third‑party services like Zillow/Redfin APIs?
* How do we integrate with external account aggregation services without compromising privacy?

This module will be implemented during Phase 3 of the roadmap.