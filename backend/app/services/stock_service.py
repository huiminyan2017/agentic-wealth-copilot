"""Stock data service using yfinance with simple in-memory TTL cache."""

from __future__ import annotations

import time
import logging
from typing import Optional

import yfinance as yf

logger = logging.getLogger(__name__)

# ── TTL cache ─────────────────────────────────────────────────────────────────
_CACHE: dict[str, tuple[float, object]] = {}
_QUOTE_TTL   = 60    # seconds — quotes refresh every minute
_HISTORY_TTL = 300   # seconds — history refreshes every 5 minutes
_CACHE_MAX   = 200   # max entries — evict oldest when exceeded


def _cached(key: str, ttl: int, fn):
    now = time.time()
    if key in _CACHE:
        ts, val = _CACHE[key]
        if now - ts < ttl:
            return val
    val = fn()
    _CACHE[key] = (now, val)
    # Evict oldest entries if cache exceeds max size
    if len(_CACHE) > _CACHE_MAX:
        oldest = sorted(_CACHE, key=lambda k: _CACHE[k][0])
        for k in oldest[:len(_CACHE) - _CACHE_MAX]:
            del _CACHE[k]
    return val


# ── public API ────────────────────────────────────────────────────────────────

def get_quote(ticker: str) -> dict:
    """Return current quote data for a ticker."""
    def _fetch():
        try:
            t = yf.Ticker(ticker.upper())
            info = t.fast_info
            hist = t.history(period="2d")

            price      = float(info.last_price)      if info.last_price      else None
            prev_close = float(info.previous_close)  if info.previous_close  else None
            change     = round(price - prev_close, 2) if price and prev_close else None
            pct_change = round(change / prev_close * 100, 2) if change and prev_close else None

            # Pull richer info from .info (slower but more complete)
            full = t.info
            return {
                "ticker":       ticker.upper(),
                "name":         full.get("longName") or full.get("shortName", ticker),
                "price":        price,
                "prev_close":   prev_close,
                "change":       change,
                "pct_change":   pct_change,
                "open":         float(info.open)           if info.open           else None,
                "day_high":     float(info.day_high)       if info.day_high       else None,
                "day_low":      float(info.day_low)        if info.day_low        else None,
                "week52_high":  float(info.year_high)  if info.year_high  else None,
                "week52_low":   float(info.year_low)   if info.year_low   else None,
                "volume":       int(info.three_month_average_volume) if info.three_month_average_volume else None,
                "market_cap":   full.get("marketCap"),
                "pe_ratio":     full.get("trailingPE"),
                "forward_pe":   full.get("forwardPE"),
                "dividend_yield": full.get("dividendYield"),
                "sector":       full.get("sector"),
                "currency":     full.get("currency", "USD"),
            }
        except Exception as e:
            logger.warning(f"get_quote({ticker}) failed: {e}")
            return {"ticker": ticker.upper(), "error": str(e)}

    return _cached(f"quote:{ticker.upper()}", _QUOTE_TTL, _fetch)


def get_history(ticker: str, period: str = "1y") -> list[dict]:
    """Return OHLCV history as a list of dicts. period: 1mo 3mo 6mo 1y 2y 5y ytd."""
    valid_periods = {"1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max", "ytd", "1w", "5d"}
    if period not in valid_periods:
        period = "1y"

    def _fetch():
        try:
            t = yf.Ticker(ticker.upper())
            # yfinance doesn't have "1w" — map it
            yf_period = "5d" if period == "1w" else period
            df = t.history(period=yf_period)
            if df.empty:
                return []
            df = df.reset_index()
            records = []
            for _, row in df.iterrows():
                records.append({
                    "date":   row["Date"].strftime("%Y-%m-%d"),
                    "open":   round(float(row["Open"]),   2),
                    "high":   round(float(row["High"]),   2),
                    "low":    round(float(row["Low"]),    2),
                    "close":  round(float(row["Close"]),  2),
                    "volume": int(row["Volume"]),
                })
            return records
        except Exception as e:
            logger.warning(f"get_history({ticker}, {period}) failed: {e}")
            return []

    return _cached(f"hist:{ticker.upper()}:{period}", _HISTORY_TTL, _fetch)


def batch_quotes(tickers: list[str]) -> list[dict]:
    """Return quotes for multiple tickers."""
    return [get_quote(t) for t in tickers]
