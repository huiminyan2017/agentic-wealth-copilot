from __future__ import annotations

import os
import json
import re
import logging
# import pdfplumber
# from typing import Optional
from pathlib import Path
# from datetime import date, datetime
from backend.app.services.storage import parsed_dir
from backend.app.services.paystub_parser import parse_paystub
from backend.app.services.w2_parser import parse_w2
from backend.app.services.utils import detect_employer

logger = logging.getLogger(__name__)

def detect_doc_kind(filename_or_hint: str) -> str:
    f = filename_or_hint.lower()
    if "w2" in f or "w-2" in f:
        return "w2"
    if "pay" in f or "stub" in f or "adp" in f:
        return "paystub"
    return "unknown"

def sha256(p: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def ingest_documents(person: str, paths: list[Path]):
    logger.info(f"[INGEST] person={person}, num_files={len(paths)}")
    pdir = parsed_dir(person)
    index_path = pdir / "index.json"
    index = {"files": {}}  # sha256 -> record meta
    if index_path.exists():
        index = json.loads(index_path.read_text("utf-8"))

    ingested = 0
    skipped = 0
    errors: list[str] = []
    skipped_files = []
    skip_reasons = {}

    for pdf in paths:
        try:
            sha = sha256(pdf)
            sha8 = sha[:8]

            if sha in index["files"]:
                skipped += 1
                skipped_files.append({
                    "path": str(pdf),
                    "reason": "already_ingested"
                })
                skip_reasons["already_ingested"] = skip_reasons.get("already_ingested", 0) + 1
                continue

            kind = detect_doc_kind(pdf.name)
            employer = detect_employer(pdf.name)

            if kind == "w2":
                rec = parse_w2(pdf, employer, person=person, sha8=sha8)
                out = pdir / "w2" / f"{rec.year}_{sha8}.json"
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(rec.model_dump_json(indent=2), "utf-8")

            elif kind == "paystub":
                rec = parse_paystub(pdf, employee=employer, prefer_azure=False)
                out = pdir / "paystub" / f"{rec.pay_date}_{sha8}.json"
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(rec.model_dump_json(indent=2), "utf-8")

            else:
                skipped += 1
                skipped_files.append({
                    "path": str(pdf),
                    "reason": "unknown_doc_type"
                })
                skip_reasons["unknown_doc_type"] = skip_reasons.get("unknown_doc_type", 0) + 1
                continue

            index["files"][sha] = {"rel": str(pdf), "kind": kind, "employer": employer}
            ingested += 1

        except Exception as e:
            skipped += 1
            reason = "parse_error"
            skipped_files.append({
                "path": str(pdf),
                "reason": reason,
                "error": str(e)
            })
            skip_reasons[reason] = skip_reasons.get(reason, 0) + 1

    index_path.write_text(json.dumps(index, indent=2), "utf-8")

    return {
        "ingested": ingested,
        "skipped": skipped,
        "skip_reasons": skip_reasons,
        "skipped_files": skipped_files,
        "errors": errors,
    }
