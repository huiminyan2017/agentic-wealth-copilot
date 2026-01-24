from __future__ import annotations

import os
import json
import re
import logging
from pathlib import Path
from datetime import date
from backend.app.services.paths import parsed_dir
from backend.app.services.paystub_parser import parse_paystub
from backend.app.services.w2_parser import parse_w2
from backend.app.services.pdf_utils import detect_employer, sha256
from backend.app.schemas import PaystubRecordV2

logger = logging.getLogger(__name__)

def detect_doc_kind(filename_or_hint: str) -> str:
    f = filename_or_hint.lower()
    if "w2" in f or "w-2" in f:
        return "w2"
    if "pay" in f or "stub" in f or "adp" in f:
        return "paystub"
    return "unknown"

def ingest_documents(person: str, paths: list[Path]):
    logger.info(f"[INGEST] person={person}, num_files={len(paths)}")
    pdir = parsed_dir(person)
    index_path = pdir / "income_file_index.json"
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
                existing_info = index["files"][sha]
                skipped_files.append({
                    "path": str(pdf.name),  # Show just filename for cleaner UI
                    "reason": "already_ingested",
                    "details": f"Already exists as {existing_info.get('kind', 'document')}"
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
                rec_dict = parse_paystub(pdf, employee=employer)
                rec = PaystubRecordV2(**rec_dict)
                out = pdir / "paystub" / f"{rec.pay_date}_{sha8}.json"
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(rec.model_dump_json(indent=2), "utf-8")

            else:
                skipped += 1
                skipped_files.append({
                    "path": str(pdf.name),
                    "reason": "unknown_doc_type",
                    "details": f"Could not identify document type from filename"
                })
                skip_reasons["unknown_doc_type"] = skip_reasons.get("unknown_doc_type", 0) + 1
                continue

            index["files"][sha] = {"rel": str(pdf), "kind": kind, "employer": employer}
            ingested += 1

        except Exception as e:
            skipped += 1
            reason = "parse_error"
            skipped_files.append({
                "path": str(pdf.name),
                "reason": reason,
                "error": str(e),
                "details": f"Failed to parse: {str(e)[:100]}"
            })
            skip_reasons[reason] = skip_reasons.get(reason, 0) + 1
            logger.error(f"Error parsing {pdf.name}: {e}", exc_info=True)

    index_path.write_text(json.dumps(index, indent=2), "utf-8")

    return {
        "ingested": ingested,
        "skipped": skipped,
        "skip_reasons": skip_reasons,
        "skipped_files": skipped_files,
        "errors": errors,
    }
