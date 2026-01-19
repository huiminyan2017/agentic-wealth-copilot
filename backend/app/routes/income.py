from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from pathlib import Path
import hashlib

from backend.app.services.storage import repo_root
from backend.app.services.extractors import detect_doc_kind, detect_employer, ingest_documents

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

class IngestResult(BaseModel):
    ingested: int
    skipped: int
    errors: list[str] = Field(default_factory=list)

def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

@router.get("/income/scan", response_model=ScanResponse)
def scan_income(person: str) -> ScanResponse:
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
                    sha256=_sha256(p),
                )
            )
    return ScanResponse(items=candidates)

@router.post("/income/ingest", response_model=IngestResult)
def ingest_income(req: IngestRequest) -> IngestResult:
    if not req.rel_paths:
        return IngestResult(ingested=0, skipped=0, errors=[])

    root = repo_root()
    abs_paths = []
    for rel in req.rel_paths:
        p = (root / rel).resolve()
        if not p.exists():
            return IngestResult(ingested=0, skipped=0, errors=[f"Missing file: {rel}"])
        abs_paths.append(p)

    return ingest_documents(person=req.person, paths=abs_paths)