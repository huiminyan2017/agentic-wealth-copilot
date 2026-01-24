"""Alert CRUD routes and manual trigger endpoint."""

from __future__ import annotations

import uuid
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

from backend.app.services import alert_service
from backend.app.services.alert_service import AlertRule

router = APIRouter()


# ── Request schemas ───────────────────────────────────────────────────────────

class CreateAlertBody(BaseModel):
    ticker: str
    direction: Literal["up", "down", "both"] = "both"
    threshold_pct: float = 5.0
    time_range: Literal["1d", "5d", "1mo", "3mo"] = "1d"
    email: EmailStr
    enabled: bool = True


class UpdateAlertBody(BaseModel):
    direction: Optional[Literal["up", "down", "both"]] = None
    threshold_pct: Optional[float] = None
    time_range: Optional[Literal["1d", "5d", "1mo", "3mo"]] = None
    email: Optional[EmailStr] = None
    enabled: Optional[bool] = None


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/alerts/{person}")
def list_alerts(person: str):
    return {
        "person": person,
        "alerts": [r.model_dump() for r in alert_service.load_alerts(person)],
    }


@router.post("/alerts/{person}", status_code=201)
def create_alert(person: str, body: CreateAlertBody):
    rule = AlertRule(id=str(uuid.uuid4())[:8], **body.model_dump())
    alert_service.add_alert(person, rule)
    return rule.model_dump()


@router.put("/alerts/{person}/{alert_id}")
def update_alert(person: str, alert_id: str, body: UpdateAlertBody):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    rule = alert_service.update_alert(person, alert_id, **updates)
    if not rule:
        raise HTTPException(status_code=404, detail="Alert not found")
    return rule.model_dump()


@router.delete("/alerts/{person}/{alert_id}")
def delete_alert(person: str, alert_id: str):
    if not alert_service.delete_alert(person, alert_id):
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"deleted": True}


@router.post("/alerts/{person}/check")
def trigger_check(person: str):
    """Manually run alert check for one person (bypasses market-hours gate)."""
    triggered = alert_service.check_alerts_for_person(person)
    return {"person": person, "triggered": triggered}
