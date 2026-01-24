from __future__ import annotations

import re
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from pathlib import Path
from datetime import date, datetime
import hashlib
import json

_SAFE_NAME = re.compile(r'^[A-Za-z][A-Za-z0-9_-]*$')

def _validate_person(name: str) -> None:
    if not _SAFE_NAME.match(name):
        raise HTTPException(status_code=400, detail="Invalid person name")

from backend.app.services.paths import repo_root, parsed_dir
from backend.app.services.income_ingestion import detect_doc_kind, detect_employer, ingest_documents
from backend.app.services.pdf_utils import sha256
from backend.app.services.income_trends import calculate_income_trends

router = APIRouter()

class ScanItem(BaseModel):
    person: str
    kind: str  # "w2" or "paystub" or "unknown"
    employer: str  # "microsoft" / "u_of_utah" / "unknown"
    rel_path: str  # path relative to repo root
    sha256: str

class ScanResponse(BaseModel):
    items: list[ScanItem]

class IngestRequest(BaseModel):
    person: str = Field(..., min_length=1)
    rel_paths: list[str] = Field(default_factory=list)

class SkippedFile(BaseModel):
    path: str
    reason: str
    details: Optional[str] = None
    error: Optional[str] = None

class IngestResult(BaseModel):
    ingested: int
    skipped: int
    skip_reasons: dict[str, int] = Field(default_factory=dict)
    skipped_files: list[SkippedFile] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

@router.get("/income/scan", response_model=ScanResponse)
def scan_income(person: str) -> ScanResponse:
    _validate_person(person)
    root = repo_root()
    base = root / "data" / "raw" / person
    if not base.exists():
        raise HTTPException(status_code=404, detail=f"Missing folder: {base}")

    candidates = []
    for sub in ["w2", "paystub"]:
        d = base / sub
        if not d.exists():
            continue
        for p in sorted(d.glob("*.pdf")):
            rel = p.relative_to(root).as_posix()
            # lightweight detection based on filename for now (fast preview)
            kind = detect_doc_kind(p.name)
            employer = detect_employer(p.name)
            candidates.append(
                ScanItem(
                    person=person,
                    kind=kind,
                    employer=employer,
                    rel_path=rel,
                    sha256=sha256(p),
                )
            )
    return ScanResponse(items=candidates)

@router.post("/income/ingest", response_model=IngestResult)
def ingest_income(req: IngestRequest) -> IngestResult:
    _validate_person(req.person)
    if not req.rel_paths:
        return IngestResult(ingested=0, skipped=0)

    root = repo_root()
    abs_paths = []
    for rel in req.rel_paths:
        p = (root / rel).resolve()
        if not p.exists():
            return IngestResult(ingested=0, skipped=0, errors=[f"Missing file: {rel}"])
        abs_paths.append(p)

    return ingest_documents(person=req.person, paths=abs_paths)

# ============================================================================
# Analytics Endpoints
# ============================================================================

@router.get("/income/trends")
def income_trends(person: str):
    """
    Returns monthly time series for gross/net/taxes/deductions, plus simple insights.
    Reads from data/parsed/<person>/paystub/*.json and data/parsed/<person>/w2/*.json
    
    Returns empty result with message if no documents found (instead of 404).
    """
    result = calculate_income_trends(person)
    
    # Add a message field to indicate if data is missing
    if not result["series"] and not result["w2_annual_summaries"]:
        result["message"] = f"No income documents found for {person}. Please upload paystubs or W-2s first."
        result["has_data"] = False
    else:
        result["has_data"] = True
    
    return result


# ============================================================================
# Income Intelligence Agent Endpoint
# ============================================================================

class AnalyzeRequest(BaseModel):
    person: str = Field(..., min_length=1, description="Person/folder name to analyze")

class AnalyzeResponse(BaseModel):
    report: str = Field(..., description="Markdown formatted analysis report")
    insights: list[dict] = Field(default_factory=list, description="List of insights")
    actions: list[dict] = Field(default_factory=list, description="Recommended actions")
    anomalies: list[dict] = Field(default_factory=list, description="Detected anomalies")
    data_summary: dict = Field(default_factory=dict, description="Summary of analyzed data")
    trace: list[str] = Field(default_factory=list, description="Execution trace for debugging")
    error: Optional[str] = Field(None, description="Error message if analysis failed")


@router.post("/income/analyze", response_model=AnalyzeResponse)
def analyze_income(req: AnalyzeRequest) -> AnalyzeResponse:
    """
    Run the Income Intelligence Agent to analyze income and taxes.
    
    The agent autonomously:
    1. Loads parsed income data (paystubs and W2s)
    2. Computes income trends (monthly, yearly, tax rates)
    3. Detects anomalies (tax rate changes, income volatility, SS cap hits)
    4. Generates actionable insights
    5. Proposes specific actions
    
    Returns a comprehensive analysis report with insights and recommended actions.
    """
    from agents.income_analysis import run_income_analysis
    
    try:
        result = run_income_analysis(person=req.person)
        return AnalyzeResponse(**result)
    except Exception as e:
        return AnalyzeResponse(
            report=f"❌ Analysis failed: {str(e)}",
            error=str(e),
            trace=[f"analyze_income:error:{e}"]
        )