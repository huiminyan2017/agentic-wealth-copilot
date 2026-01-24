"""Background scheduler for periodic stock alert checks.

The scheduler fires every 2 hours. The alert_service itself gates on
market hours, so this just needs to run at a regular cadence.
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from backend.app.services.alert_service import check_all_alerts

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def start_scheduler() -> None:
    global _scheduler
    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(
        check_all_alerts,
        trigger="interval",
        hours=2,
        id="stock_alert_check",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=300,  # allow up to 5 min late start
    )
    _scheduler.start()
    logger.info("Stock alert scheduler started (interval: 2h, market-hours only)")


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Stock alert scheduler stopped")
