#!/usr/bin/env python3
"""
Unified document ingestion tool for paystubs and W-2s.

This tool handles ingestion of financial documents with optional force re-ingestion.

Usage:
    # Ingest all paystubs for a person (skip already ingested)
    python scripts/income_ingest_tool.py paystub --person Huimin

    # Force re-ingest all paystubs (clear index first)
    python scripts/income_ingest_tool.py paystub --person Huimin --force

    # Ingest and validate parser invariants
    python scripts/income_ingest_tool.py paystub --person Huimin --force --validate-result

    # Ingest all W-2s for a person
    python scripts/income_ingest_tool.py w2 --person Bao

    # Force re-ingest W-2s
    python scripts/income_ingest_tool.py w2 --person Huimin --force

    # Ingest all document types for a person
    python scripts/income_ingest_tool.py all --person Huimin

    # Filter by date pattern (for paystubs)
    python scripts/income_ingest_tool.py paystub --person Huimin --date 2025
    
    # Validate only (no ingestion) - check existing parsed files
    python scripts/income_ingest_tool.py paystub --person Huimin --validate-result --skip-ingest
"""
import argparse
import json
import sys
import logging
from pathlib import Path
from typing import Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Initialize logging BEFORE importing services
from backend.app.logging import configure_logging
configure_logging()

from backend.app.services.income_ingestion import ingest_documents
from backend.app.services.utils import sha256
from backend.app.services.storage import repo_root, parsed_dir

logger = logging.getLogger(__name__)

RAW_DIR = PROJECT_ROOT / "data" / "raw"

# Validation tolerance for parser invariant checks
VALIDATION_TOLERANCE = 0.02


# =============================================================================
# Validation functions (merged from validate_paystub_parser_invariant.py)
# =============================================================================

def validate_sum(section: dict) -> tuple[float, float, float]:
    """Validate that section.value == sum(section.details). Returns (value, sum, diff)."""
    value = section.get("value", 0.0)
    details = section.get("details", {})
    details_sum = sum(details.values())
    diff = abs(value - details_sum)
    return value, details_sum, diff


def validate_parsed_paystubs(person: str, verbose: bool = True) -> dict:
    """
    Validate all parsed paystubs for a person.
    
    Validates:
      1. Net pay:    validation.net_pay_diff ≈ 0
      2. Taxes:      taxes.value = sum(taxes.details)
      3. Pretax:     pretax_deductions.value = sum(pretax_deductions.details)
      4. Aftertax:   aftertax_deductions.value = sum(aftertax_deductions.details)
    
    Returns dict with counts and failure lists.
    """
    pdir = parsed_dir(person) / "paystub"
    
    if not pdir.exists():
        return {"count": 0, "net_failures": [], "taxes_failures": [], 
                "pretax_failures": [], "aftertax_failures": []}
    
    jsons = sorted(pdir.glob("*.json"))
    
    results = {
        "count": len(jsons),
        "net_failures": [],      # (name, validation_value)
        "taxes_failures": [],    # (name, value, sum, diff)
        "pretax_failures": [],   # (name, value, sum, diff)
        "aftertax_failures": [], # (name, value, sum, diff)
    }
    
    for json_path in jsons:
        with open(json_path) as f:
            data = json.load(f)
        name = json_path.stem
        
        # 1. Net pay validation (validation.net_pay_diff should be ~0)
        validation = data.get("validation", {})
        # Support both old format (value) and new format (net_pay_diff)
        net_pay_diff = validation.get("net_pay_diff") or validation.get("value")
        if net_pay_diff is not None and abs(net_pay_diff) > VALIDATION_TOLERANCE:
            results["net_failures"].append((name, net_pay_diff))
        
        # 2. Taxes validation - use validation.tax_sum_diff if available
        tax_sum_diff = validation.get("tax_sum_diff")
        if tax_sum_diff is not None:
            if abs(tax_sum_diff) > VALIDATION_TOLERANCE:
                taxes = data.get("taxes", {})
                val = taxes.get("value", 0)
                sum_val = sum(taxes.get("details", {}).values())
                results["taxes_failures"].append((name, val, sum_val, tax_sum_diff))
        elif "taxes" in data:
            val, sum_val, diff = validate_sum(data["taxes"])
            if diff > VALIDATION_TOLERANCE:
                results["taxes_failures"].append((name, val, sum_val, diff))
        
        # 3. Pretax deductions validation
        pretax_sum_diff = validation.get("pretax_sum_diff")
        if pretax_sum_diff is not None:
            if abs(pretax_sum_diff) > VALIDATION_TOLERANCE:
                pretax = data.get("pretax_deductions", {})
                val = pretax.get("value", 0)
                sum_val = sum(pretax.get("details", {}).values())
                results["pretax_failures"].append((name, val, sum_val, pretax_sum_diff))
        elif "pretax_deductions" in data:
            val, sum_val, diff = validate_sum(data["pretax_deductions"])
            if diff > VALIDATION_TOLERANCE:
                results["pretax_failures"].append((name, val, sum_val, diff))
        
        # 4. Aftertax deductions validation
        aftertax_sum_diff = validation.get("aftertax_sum_diff")
        if aftertax_sum_diff is not None:
            if abs(aftertax_sum_diff) > VALIDATION_TOLERANCE:
                aftertax = data.get("aftertax_deductions", {})
                val = aftertax.get("value", 0)
                sum_val = sum(aftertax.get("details", {}).values())
                results["aftertax_failures"].append((name, val, sum_val, aftertax_sum_diff))
        elif "aftertax_deductions" in data:
            val, sum_val, diff = validate_sum(data["aftertax_deductions"])
            if diff > VALIDATION_TOLERANCE:
                results["aftertax_failures"].append((name, val, sum_val, diff))
    
    return results


def print_validation_results(person: str, results: dict, verbose: bool = True) -> int:
    """Print validation results and return total failure count."""
    if not verbose:
        total = (len(results["net_failures"]) + len(results["taxes_failures"]) + 
                 len(results["pretax_failures"]) + len(results["aftertax_failures"]))
        return total
    
    print(f"\n🔍 Validation results for {person}:")
    print(f"   Total parsed JSONs: {results['count']}")
    
    # Net pay
    net = results["net_failures"]
    if net:
        print(f"\n   ❌ Net pay failures ({len(net)}):")
        for name, val in net[:5]:
            print(f"      {name}: net_pay_diff={val:.2f}")
        if len(net) > 5:
            print(f"      ... and {len(net) - 5} more")
    else:
        print(f"   ✅ Net pay: all pass")
    
    # Taxes
    taxes = results["taxes_failures"]
    if taxes:
        print(f"\n   ❌ Taxes failures ({len(taxes)}):")
        for name, val, sum_val, diff in taxes[:5]:
            print(f"      {name}: value={val:.2f}, sum={sum_val:.2f}, diff={diff:.2f}")
        if len(taxes) > 5:
            print(f"      ... and {len(taxes) - 5} more")
    else:
        print(f"   ✅ Taxes: all pass")
    
    # Pretax
    pretax = results["pretax_failures"]
    if pretax:
        print(f"\n   ❌ Pretax deductions failures ({len(pretax)}):")
        for name, val, sum_val, diff in pretax[:5]:
            print(f"      {name}: value={val:.2f}, sum={sum_val:.2f}, diff={diff:.2f}")
        if len(pretax) > 5:
            print(f"      ... and {len(pretax) - 5} more")
    else:
        print(f"   ✅ Pretax deductions: all pass")
    
    # Aftertax
    aftertax = results["aftertax_failures"]
    if aftertax:
        print(f"\n   ❌ Aftertax deductions failures ({len(aftertax)}):")
        for name, val, sum_val, diff in aftertax[:5]:
            print(f"      {name}: value={val:.2f}, sum={sum_val:.2f}, diff={diff:.2f}")
        if len(aftertax) > 5:
            print(f"      ... and {len(aftertax) - 5} more")
    else:
        print(f"   ✅ Aftertax deductions: all pass")
    
    return len(net) + len(taxes) + len(pretax) + len(aftertax)


# =============================================================================
# Common utilities
# =============================================================================

def get_all_persons() -> list[str]:
    """Discover all person folders in data/raw/ (excluding hidden folders)."""
    if not RAW_DIR.exists():
        return []
    persons = []
    for item in RAW_DIR.iterdir():
        if item.is_dir() and not item.name.startswith('.'):
            persons.append(item.name)
    return sorted(persons)


def find_folder(person: str, folder_names: list[str]) -> Optional[Path]:
    """Find first existing folder from list of possible names."""
    for name in folder_names:
        folder = RAW_DIR / person / name
        if folder.exists():
            return folder
    return None


def get_pdfs(person: str, doc_type: str, date_filter: Optional[str] = None) -> list[Path]:
    """Get PDF paths for a person and document type, optionally filtered by date."""
    if doc_type == "paystub":
        folder = find_folder(person, ["paystub", "Paystub"])
    else:  # w2
        folder = find_folder(person, ["w2", "W2"])
    
    if not folder:
        return []
    
    pdfs = sorted(folder.glob("*.pdf"))
    
    # Filter by date pattern if specified
    if date_filter:
        pdfs = [p for p in pdfs if date_filter in p.name]
    
    return pdfs


def clear_from_index(person: str, pdf_hashes: set[str]) -> int:
    """Remove entries from index by their SHA256 hashes. Returns count removed."""
    pdir = parsed_dir(person)
    index_path = pdir / "index.json"
    
    if not index_path.exists():
        return 0
    
    with open(index_path, 'r') as f:
        index = json.load(f)
    
    original_count = len(index.get("files", {}))
    
    # Remove entries matching the hashes
    index["files"] = {
        sha: entry for sha, entry in index.get("files", {}).items()
        if sha not in pdf_hashes
    }
    
    # Write updated index
    with open(index_path, 'w') as f:
        json.dump(index, f, indent=2)
    
    return original_count - len(index["files"])


def delete_parsed_files(person: str, doc_type: str) -> int:
    """Delete existing parsed JSON files. Returns count deleted."""
    pdir = parsed_dir(person)
    parsed_doc_dir = pdir / doc_type
    
    if not parsed_doc_dir.exists():
        return 0
    
    deleted = 0
    for parsed_file in parsed_doc_dir.glob("*.json"):
        parsed_file.unlink()
        deleted += 1
    
    return deleted


# =============================================================================
# Ingestion functions
# =============================================================================

def ingest_docs(
    person: str,
    doc_type: str,
    force: bool = False,
    date_filter: Optional[str] = None,
    verbose: bool = True,
    validate_result: bool = False,
    skip_ingest: bool = False
) -> dict:
    """
    Ingest documents for a person.
    
    Args:
        person: Person name
        doc_type: "paystub" or "w2"
        force: If True, clear index and re-ingest all
        date_filter: Optional date pattern to filter files (e.g., "2025")
        verbose: Print progress messages
        validate_result: If True, validate parsed results after ingestion
        skip_ingest: If True, skip ingestion and only validate
        
    Returns:
        Ingestion result dict (includes validation_failures if validate_result=True)
    """
    result = {"ingested": 0, "skipped": 0, "validation_failures": 0}
    
    # Skip ingestion if requested (validate-only mode)
    if skip_ingest:
        if verbose:
            print(f"⏭️  Skipping ingestion (validate-only mode)")
    else:
        pdfs = get_pdfs(person, doc_type, date_filter)
        
        if not pdfs:
            if verbose:
                print(f"No {doc_type} PDFs found for {person}" + 
                      (f" matching '{date_filter}'" if date_filter else ""))
            return result
        
        if verbose:
            print(f"Found {len(pdfs)} {doc_type} PDF(s) for {person}")
            if date_filter:
                print(f"  (filtered by: {date_filter})")
        
        # Force re-ingest: clear index entries and parsed files
        if force:
            if verbose:
                print(f"\n🔄 Force mode: clearing existing data...")
            
            # Calculate hashes for all PDFs
            pdf_hashes = {sha256(pdf) for pdf in pdfs}
            
            # Clear from index
            removed = clear_from_index(person, pdf_hashes)
            if verbose:
                print(f"  Removed {removed} entries from index")
            
            # Delete parsed files
            deleted = delete_parsed_files(person, doc_type)
            if verbose:
                print(f"  Deleted {deleted} parsed {doc_type} files")
        
        # Ingest
        if verbose:
            print(f"\n📥 Ingesting {len(pdfs)} {doc_type}(s)...")
        
        ingest_result = ingest_documents(person=person, paths=pdfs)
        result["ingested"] = ingest_result.get("ingested", 0)
        result["skipped"] = ingest_result.get("skipped", 0)
        
        # Print results
        if verbose:
            print(f"\n✅ Ingestion complete:")
            print(f"  Ingested: {result['ingested']}")
            print(f"  Skipped: {result['skipped']}")
            
            if ingest_result.get('skip_reasons'):
                print(f"\n  Skip reasons:")
                for reason, count in ingest_result['skip_reasons'].items():
                    print(f"    {reason}: {count}")
            
            if ingest_result.get('skipped_files'):
                print(f"\n  Skipped files:")
                for item in ingest_result['skipped_files'][:5]:  # Show first 5
                    print(f"    - {Path(item['path']).name}: {item['reason']}")
                if len(ingest_result['skipped_files']) > 5:
                    print(f"    ... and {len(ingest_result['skipped_files']) - 5} more")
            
            if ingest_result.get('errors'):
                print(f"\n⚠️  Errors:")
                for err in ingest_result['errors'][:5]:
                    print(f"    - {err}")
    
    # Validate parsed results if requested (paystubs only)
    if validate_result and doc_type == "paystub":
        validation_results = validate_parsed_paystubs(person, verbose=verbose)
        failures = print_validation_results(person, validation_results, verbose=verbose)
        result["validation_failures"] = failures
        
        if verbose:
            if failures == 0:
                print(f"\n✅ All validations passed!")
            else:
                print(f"\n⚠️  {failures} validation failure(s)")
    
    return result


# =============================================================================
# Main CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Unified document ingestion tool for paystubs and W-2s",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        "doc_type",
        choices=["paystub", "w2", "all"],
        help="Document type to ingest"
    )
    parser.add_argument(
        "--person", "-p",
        required=True,
        help="Person name (required)"
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Force re-ingestion (clear index first)"
    )
    parser.add_argument(
        "--date", "-d",
        help="Filter by date pattern (e.g., '2025', '2025-01')"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Only show summary"
    )
    parser.add_argument(
        "--validate-result", "-v",
        action="store_true",
        help="Validate parser invariants after ingestion (paystubs only)"
    )
    parser.add_argument(
        "--skip-ingest",
        action="store_true",
        help="Skip ingestion, only validate existing parsed files"
    )
    
    args = parser.parse_args()
    
    # Validate person exists
    persons = get_all_persons()
    if args.person not in persons:
        print(f"❌ Person '{args.person}' not found.")
        print(f"   Available: {', '.join(persons)}")
        sys.exit(1)
    
    verbose = not args.quiet
    total_ingested = 0
    total_skipped = 0
    total_validation_failures = 0
    
    # Determine which doc types to process
    if args.doc_type == "all":
        doc_types = ["paystub", "w2"]
    else:
        doc_types = [args.doc_type]
    
    # Process each doc type
    for doc_type in doc_types:
        if verbose and len(doc_types) > 1:
            print(f"\n{'='*60}")
            print(f"Processing {doc_type} for {args.person}")
            print(f"{'='*60}")
        
        result = ingest_docs(
            person=args.person,
            doc_type=doc_type,
            force=args.force,
            date_filter=args.date,
            verbose=verbose,
            validate_result=args.validate_result,
            skip_ingest=args.skip_ingest
        )
        
        total_ingested += result.get("ingested", 0)
        total_skipped += result.get("skipped", 0)
        total_validation_failures += result.get("validation_failures", 0)
    
    # Final summary for "all" mode
    if args.doc_type == "all" and verbose:
        print(f"\n{'='*60}")
        print(f"📊 Total: {total_ingested} ingested, {total_skipped} skipped")
        if args.validate_result:
            print(f"   Validation failures: {total_validation_failures}")
    
    # Exit with error if validation failures
    if args.validate_result and total_validation_failures > 0:
        sys.exit(1)
    
    sys.exit(0)


if __name__ == "__main__":
    main()
