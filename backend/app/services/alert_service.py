"""Stock price alert service — evaluate rules and dispatch email notifications."""

from __future__ import annotations

import json
import logging
import smtplib
import uuid
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from pathlib import Path
from typing import Literal, Optional
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from backend.app.services.stock_service import get_history, get_quote
from backend.app.services.paths import PARSED_DATA_DIR
from backend.app.settings import settings

logger = logging.getLogger(__name__)
ET = ZoneInfo("America/New_York")

_COOLDOWN_HOURS = 24


# ── Alert data model ───────────────────────────────────────────────────────────

class AlertRule(BaseModel):
    id: str
    ticker: str
    direction: Literal["up", "down", "both"] = "both"
    threshold_pct: float = 5.0
    time_range: Literal["1d", "5d", "1mo", "3mo"] = "1d"
    email: str
    enabled: bool = True
    last_triggered: Optional[str] = None   # ISO datetime (UTC)
    last_change_pct: Optional[float] = None


# ── Alert persistence ──────────────────────────────────────────────────────────

def _alerts_path(person: str) -> Path:
    p = PARSED_DATA_DIR / person
    p.mkdir(parents=True, exist_ok=True)
    return p / "alerts.json"


def load_alerts(person: str) -> list[AlertRule]:
    path = _alerts_path(person)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
        return [AlertRule(**r) for r in data.get("alerts", [])]
    except Exception as e:
        logger.warning("Failed to load alerts for %s: %s", person, e)
        return []


def save_alerts(person: str, alerts: list[AlertRule]) -> None:
    _alerts_path(person).write_text(
        json.dumps({"alerts": [r.model_dump() for r in alerts]}, indent=2)
    )


def add_alert(person: str, rule: AlertRule) -> AlertRule:
    alerts = load_alerts(person)
    alerts.append(rule)
    save_alerts(person, alerts)
    return rule


def update_alert(person: str, alert_id: str, **kwargs) -> Optional[AlertRule]:
    alerts = load_alerts(person)
    for i, a in enumerate(alerts):
        if a.id == alert_id:
            updated = a.model_copy(update=kwargs)
            alerts[i] = updated
            save_alerts(person, alerts)
            return updated
    return None


def delete_alert(person: str, alert_id: str) -> bool:
    alerts = load_alerts(person)
    new_alerts = [a for a in alerts if a.id != alert_id]
    if len(new_alerts) == len(alerts):
        return False
    save_alerts(person, new_alerts)
    return True


# ── Market hours ──────────────────────────────────────────────────────────────

def is_market_open() -> bool:
    """Return True if US stock market is currently open (9:30–16:00 ET, Mon–Fri)."""
    now = datetime.now(ET)
    if now.weekday() >= 5:
        return False
    open_t  = now.replace(hour=9,  minute=30, second=0, microsecond=0)
    close_t = now.replace(hour=16, minute=0,  second=0, microsecond=0)
    return open_t <= now <= close_t


# ── Price change ──────────────────────────────────────────────────────────────

def _price_change(ticker: str, time_range: str) -> Optional[tuple[float, float]]:
    """Return (pct_change, current_price) for the given time range, or None."""
    if time_range == "1d":
        q = get_quote(ticker)
        if "error" in q or q.get("pct_change") is None or q.get("price") is None:
            return None
        return float(q["pct_change"]), float(q["price"])

    period_map = {"5d": "5d", "1mo": "1mo", "3mo": "3mo"}
    history = get_history(ticker, period_map.get(time_range, "5d"))
    if len(history) < 2:
        return None
    baseline = history[0]["close"]
    current  = history[-1]["close"]
    if baseline == 0:
        return None
    return round((current - baseline) / baseline * 100, 2), current


# ── Email ─────────────────────────────────────────────────────────────────────

def _send_alert_email(
    to: str,
    ticker: str,
    change_pct: float,
    current_price: float,
    threshold_pct: float,
    time_range: str,
) -> None:
    if not all([settings.smtp_host, settings.smtp_user, settings.smtp_password]):
        logger.warning("SMTP not configured — skipping email for %s", ticker)
        return

    arrow   = "↑" if change_pct > 0 else "↓"
    subject = f"[Stock Alert] {ticker} {arrow}{abs(change_pct):.2f}% over {time_range}"
    body    = (
        f"Stock Alert Triggered\n"
        f"{'─' * 40}\n\n"
        f"Ticker        : {ticker}\n"
        f"Change        : {change_pct:+.2f}% over {time_range}\n"
        f"Current Price : ${current_price:.2f}\n"
        f"Threshold     : ±{threshold_pct}%\n\n"
        f"Triggered at {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n"
    )

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"]    = settings.smtp_from or settings.smtp_user
    msg["To"]      = to

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
        logger.info("Alert email sent: %s → %s", ticker, to)
    except Exception as e:
        logger.error("Failed to send alert email for %s: %s", ticker, e)


# ── Evaluation ────────────────────────────────────────────────────────────────

def _on_cooldown(rule: AlertRule) -> bool:
    if not rule.last_triggered:
        return False
    last = datetime.fromisoformat(rule.last_triggered)
    return datetime.utcnow() - last < timedelta(hours=_COOLDOWN_HOURS)


def check_alerts_for_person(person: str) -> list[str]:
    """Evaluate all enabled alerts for one person.

    Returns a list of human-readable strings for triggered alerts.
    Persists updated last_triggered / last_change_pct back to disk.
    """
    alerts  = load_alerts(person)
    messages: list[str] = []
    changed = False

    for i, rule in enumerate(alerts):
        if not rule.enabled or _on_cooldown(rule):
            continue

        result = _price_change(rule.ticker, rule.time_range)
        if result is None:
            continue
        pct, price = result

        fired = (
            (rule.direction == "up"   and pct >=  rule.threshold_pct) or
            (rule.direction == "down" and pct <= -rule.threshold_pct) or
            (rule.direction == "both" and abs(pct) >= rule.threshold_pct)
        )

        if fired:
            logger.info("Alert fired: %s / %s  %+.2f%%", person, rule.ticker, pct)
            alerts[i] = rule.model_copy(update={
                "last_triggered": datetime.utcnow().isoformat(),
                "last_change_pct": pct,
            })
            changed = True
            messages.append(f"{rule.ticker}: {pct:+.2f}% over {rule.time_range}")
            _send_alert_email(rule.email, rule.ticker, pct, price, rule.threshold_pct, rule.time_range)

    if changed:
        save_alerts(person, alerts)

    return messages


def check_all_alerts() -> None:
    """Scan every person's alerts and evaluate them. Called by the scheduler."""
    if not is_market_open():
        logger.debug("Market closed — skipping scheduled alert check")
        return

    logger.info("Running scheduled stock alert check…")
    if not PARSED_DATA_DIR.exists():
        return

    for person_dir in sorted(PARSED_DATA_DIR.iterdir()):
        if person_dir.is_dir() and not person_dir.name.startswith("_"):
            if (person_dir / "alerts.json").exists():
                triggered = check_alerts_for_person(person_dir.name)
                if triggered:
                    logger.info("Triggered for %s: %s", person_dir.name, triggered)
