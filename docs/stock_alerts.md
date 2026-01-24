# Stock Price Alerts

The stock alert system lets you define rules that trigger an email notification when a stock moves beyond a configured threshold over a chosen time window.

---

## Alert Rule Model

Stored in `data/parsed/<person>/alerts.json`.

```json
{
  "id": "a1b2c3d4",
  "ticker": "MSFT",
  "direction": "down",
  "threshold_pct": 5.0,
  "time_range": "1d",
  "email": "you@example.com",
  "enabled": true,
  "last_triggered": "2026-03-14T15:30:00",
  "last_change_pct": -6.2
}
```

| Field | Type | Description |
|---|---|---|
| `id` | string | Random 8-char ID |
| `ticker` | string | Stock ticker symbol |
| `direction` | `up` / `down` / `both` | Which direction triggers the alert |
| `threshold_pct` | float | Minimum % move to trigger (e.g., `5.0` = 5%) |
| `time_range` | `1d` / `5d` / `1mo` / `3mo` | Window over which to measure the move |
| `email` | string | Recipient for alert emails |
| `enabled` | bool | Whether the alert is active |
| `last_triggered` | ISO datetime (UTC) | When the alert last fired |
| `last_change_pct` | float | The % change that caused the last trigger |

---

## Trigger Logic

For `time_range = "1d"`: uses the `pct_change` field from the live quote (today vs. previous close).

For longer ranges: fetches OHLCV history, compares first close to latest close.

```
pct_change = (current_price - baseline_price) / baseline_price * 100
```

Firing conditions:
- `direction = "up"`:   fires when `pct_change >= threshold_pct`
- `direction = "down"`: fires when `pct_change <= -threshold_pct`
- `direction = "both"`: fires when `abs(pct_change) >= threshold_pct`

**Cooldown:** After an alert fires, it will not fire again for 24 hours. This prevents email spam if the condition stays met across multiple scheduler runs.

---

## Scheduler

**File:** `backend/app/services/scheduler.py`

Uses APScheduler `BackgroundScheduler`. Started automatically via FastAPI's lifespan on server boot.

```
Interval: every 2 hours
Job:      check_all_alerts()
```

`check_all_alerts()` is gated by `is_market_open()`:

```python
def is_market_open() -> bool:
    # True only Mon–Fri, 9:30 AM – 4:00 PM US Eastern Time
```

If the market is closed (evenings, weekends, holidays), the job returns immediately without fetching any prices. This avoids unnecessary yfinance API calls.

To manually trigger a check (bypassing the market-hours gate), use the API:
```
POST /api/alerts/{person}/check
```

---

## Email Configuration

SMTP credentials are configured exclusively via environment variables in `.env`:

```bash
SMTP_HOST=smtp-mail.outlook.com   # or smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@hotmail.com
SMTP_PASSWORD=your-password       # use an App Password if 2FA is enabled
SMTP_FROM=you@hotmail.com         # optional; defaults to SMTP_USER
SMTP_USE_TLS=true
```

Email sending uses Python's stdlib `smtplib` with STARTTLS. If SMTP is not configured, alerts still fire and are logged, but no email is sent.

**Example email:**
```
Subject: [Stock Alert] MSFT ↓6.20% over 1d

Stock Alert Triggered
────────────────────────────────────────

Ticker        : MSFT
Change        : -6.20% over 1d
Current Price : $389.45
Threshold     : ±5%

Triggered at 2026-03-14 15:30 UTC
```

---

## API Reference

All endpoints are prefixed with `/api`.

| Method | Path | Description |
|---|---|---|
| `GET` | `/alerts/{person}` | List all alert rules for a person |
| `POST` | `/alerts/{person}` | Create a new alert rule |
| `PUT` | `/alerts/{person}/{id}` | Update an alert rule (enable/disable, change threshold, etc.) |
| `DELETE` | `/alerts/{person}/{id}` | Delete an alert rule |
| `POST` | `/alerts/{person}/check` | Manually trigger check for a person (ignores market hours) |

**Create body:**
```json
{
  "ticker": "AAPL",
  "direction": "both",
  "threshold_pct": 5.0,
  "time_range": "1d",
  "email": "you@example.com",
  "enabled": true
}
```

---

## UI

The **⚡ Price Alerts** expander on the Investing & Trading page:

- Shows a **warning banner** at the top of the page when any alert triggered in the past 24 hours
- Lists configured alerts with direction, threshold, period, recipient email, last-trigger status
- Toggle on/off per alert
- Delete alert
- Form to add a new alert

The expander auto-opens when there are recently-triggered alerts.
