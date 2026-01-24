# Investing & Trading Module

The Investing & Trading page (`frontend/pages/3_Investing_&_Trading.py`) provides a real-time stock watchlist, price charts, and configurable price alerts with email notifications.

---

## Components

### 1. Stock Watchlist

Per-person watchlist stored in `data/parsed/<person>/watchlist.json`.

**API endpoints (backend/app/routes/stocks.py):**
```
GET  /api/stocks/watchlist/{person}         → {"tickers": ["MSFT", "AAPL", ...]}
PUT  /api/stocks/watchlist/{person}         ← {"tickers": [...]}
```

**UI behavior:** Watchlist is loaded into `st.session_state` on first visit (or when person changes). Add/remove operations update session state immediately and persist to the API in the background, avoiding Streamlit cache race conditions.

**Preset categories:**
- Tech: MSFT, AAPL, NVDA, GOOGL, META, AMZN
- Consumer: COST, WMT, TGT, NKE
- EV / AI: TSLA, PLTR, AMD
- Finance: BRK-B, JPM, V, MA
- Index: SPY, QQQ, VTI, VOO

---

### 2. Real-Time Quotes

Fetched in a single batch call to avoid N+1 requests.

```
GET /api/stocks/quotes?tickers=MSFT,AAPL,NVDA
```

**Fields returned per ticker:** `price`, `change`, `pct_change`, `day_high`, `day_low`, `week52_high`, `week52_low`, `market_cap`, `pe_ratio`, `forward_pe`, `dividend_yield`, `sector`, `name`, `currency`

**Caching:** 60-second TTL on the frontend (`st.cache_data`). The backend also caches via an in-memory TTL dict in `stock_service.py`.

---

### 3. Price Charts

```
GET /api/stocks/history/{ticker}?period=1y
```

**Supported periods:** `1w`, `1mo`, `3mo`, `6mo`, `1y`, `2y`, `5y`

Rendered as a Plotly candlestick chart (OHLCV) with a volume bar chart below. Period selector in the UI maps `1W → 5d` for the yfinance API call.

Stats row above the chart: price + delta, day range, 52-week range, market cap, P/E, dividend yield.

---

### 4. Stock Service
**File:** `backend/app/services/stock_service.py`

Thin wrapper around yfinance with an in-memory TTL cache.

```python
get_quote(ticker)           # Single quote dict
get_history(ticker, period) # List of {date, open, high, low, close, volume}
batch_quotes(tickers)       # List of quote dicts
```

**Cache TTLs:**
- Quotes: 60 seconds (`_QUOTE_TTL`)
- History: 300 seconds (`_HISTORY_TTL`)

**Known attribute:** yfinance `fast_info` uses `year_high`/`year_low` (not `fifty_two_week_high`/`fifty_two_week_low`).

---

## Price Alerts

See [stock_alerts.md](stock_alerts.md) for full detail on the alert system, scheduler, and email configuration.

**Quick summary:** Each alert rule specifies a ticker, direction (up/down/both), threshold percentage, time range (1d/5d/1mo/3mo), and recipient email. The backend checks all alerts every 2 hours during US market hours and sends an email when a rule fires. A 24-hour cooldown prevents repeated notifications.
