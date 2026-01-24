"""Stock routes — watchlist CRUD, quotes, and price history."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.app.services import stock_service
from backend.app.services.paths import parsed_dir

router = APIRouter()

# ── watchlist persistence ─────────────────────────────────────────────────────

def _watchlist_path(person: str) -> Path:
    return parsed_dir(person) / "watchlist.json"


def _load_watchlist(person: str) -> list[str]:
    p = _watchlist_path(person)
    if not p.exists():
        return []
    return json.loads(p.read_text()).get("tickers", [])


def _save_watchlist(person: str, tickers: list[str]):
    p = _watchlist_path(person)
    p.write_text(json.dumps({"tickers": tickers}, indent=2))


# ── schemas ───────────────────────────────────────────────────────────────────

class WatchlistUpdate(BaseModel):
    tickers: List[str]


# ── routes ────────────────────────────────────────────────────────────────────

@router.get("/stocks/watchlist/{person}")
def get_watchlist(person: str):
    return {"person": person, "tickers": _load_watchlist(person)}


@router.put("/stocks/watchlist/{person}")
def update_watchlist(person: str, body: WatchlistUpdate):
    tickers = [t.strip().upper() for t in body.tickers if t.strip()]
    _save_watchlist(person, tickers)
    return {"person": person, "tickers": tickers}


@router.get("/stocks/quote/{ticker}")
def get_quote(ticker: str):
    data = stock_service.get_quote(ticker)
    if "error" in data:
        raise HTTPException(status_code=404, detail=data["error"])
    return data


@router.get("/stocks/quotes")
def get_quotes(tickers: str):
    """Batch quotes. Pass tickers as comma-separated: ?tickers=MSFT,AAPL,NVDA"""
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    if not ticker_list:
        raise HTTPException(status_code=400, detail="tickers param required")
    return stock_service.batch_quotes(ticker_list)


@router.get("/stocks/history/{ticker}")
def get_history(ticker: str, period: str = "1y"):
    data = stock_service.get_history(ticker, period)
    return {"ticker": ticker.upper(), "period": period, "data": data}
