#!/usr/bin/env python
"""
Manage ground truth files for paystub and W-2 parser testing.

This script provides two operations for both document types:
1. save - Re-parse PDFs and save to groundtruth folder
2. check - Compare parsed output vs existing groundtruth

Ground truth files are committed to git for parser regression testing.

Usage:
    # Check all paystubs against existing groundtruth
    python scripts/income_groundtruth_tool.py paystub check

    # Check all W-2s against existing groundtruth  
    python scripts/income_groundtruth_tool.py w2 check

    # Force regenerate all paystub groundtruth
    python scripts/income_groundtruth_tool.py paystub save --force

    # Check specific person's W-2s
    python scripts/income_groundtruth_tool.py w2 check --person Huimin

    # Save groundtruth for specific person's paystubs
    python scripts/income_groundtruth_tool.py paystub save --person Bao --force
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.services.paystub_parser import parse_paystub
from backend.app.services.w2_parser import parse_w2
from backend.app.services.utils import detect_employer, sha256

RAW_DIR = PROJECT_ROOT / "data" / "raw"


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


def get_or_create_folder(person: str, folder_names: list[str], default: str) -> Path:
    """Get existing folder or return default path for creation."""
    existing = find_folder(person, folder_names)
    if existing:
        return existing
    return RAW_DIR / person / default


# =============================================================================
# Paystub-specific functions
# =============================================================================

def get_paystub_pdfs(person: str) -> list[Path]:
    """Get all paystub PDF paths for a person."""
    folder = find_folder(person, ["paystub", "Paystub"])
    if not folder:
        return []
    return sorted(folder.glob("*.pdf"))


def get_paystub_groundtruth_dir(person: str) -> Path:
    """Get paystub groundtruth directory for a person."""
    return get_or_create_folder(person, ["paystub_groundtruth", "Paystub_groundtruth"], "paystub_groundtruth")


def parse_paystub_to_dict(pdf_path: Path) -> dict:
    """Parse a paystub and return as dict."""
    return parse_paystub(str(pdf_path))


# =============================================================================
# W-2-specific functions
# =============================================================================

def get_w2_pdfs(person: str) -> list[Path]:
    """Get all W-2 PDF paths for a person."""
    folder = find_folder(person, ["w2", "W2"])
    if not folder:
        return []
    return sorted(folder.glob("*.pdf"))


def get_w2_groundtruth_dir(person: str) -> Path:
    """Get W-2 groundtruth directory for a person."""
    return get_or_create_folder(person, ["w2_groundtruth", "W2_groundtruth"], "w2_groundtruth")


def parse_w2_to_dict(pdf_path: Path, person: str) -> dict:
    """Parse a W-2 and return as dict."""
    employer = detect_employer(str(pdf_path))
    sha8 = sha256(pdf_path)[:8]
    record = parse_w2(pdf_path, employer, person, sha8)
    # Convert Pydantic model to dict, excluding internal fields
    data = record.model_dump()
    # Remove fields that shouldn't be in groundtruth (they vary per run)
    for key in ["extracted_text_path", "source_pdf_relpath", "notes"]:
        data.pop(key, None)
    return data


# =============================================================================
# Generic save/check functions
# =============================================================================

def save_groundtruth(
    doc_type: str,
    get_pdfs_fn,
    get_groundtruth_dir_fn,
    parse_fn,
    person: Optional[str] = None,
    verbose: bool = True
) -> tuple[int, int]:
    """
    Re-parse all PDFs and save to groundtruth folder.
    
    Args:
        doc_type: "paystub" or "w2" (for display)
        get_pdfs_fn: Function to get PDF paths for a person
        get_groundtruth_dir_fn: Function to get groundtruth dir for a person
        parse_fn: Function to parse PDF and return dict
        person: Specific person to process, or None for all
        verbose: Print progress messages
    """
    persons = [person] if person else get_all_persons()
    
    total_saved = 0
    total_errors = 0
    
    for p in persons:
        pdfs = get_pdfs_fn(p)
        if not pdfs:
            if verbose:
                print(f"No {doc_type} PDFs found for {p}")
            continue
        
        groundtruth_dir = get_groundtruth_dir_fn(p)
        groundtruth_dir.mkdir(parents=True, exist_ok=True)
        
        if verbose:
            print(f"\n{'='*60}")
            print(f"Saving {doc_type} groundtruth for {p} ({len(pdfs)} PDFs)")
            print(f"{'='*60}")
        
        for pdf_path in pdfs:
            json_name = pdf_path.stem + ".json"
            json_path = groundtruth_dir / json_name
            
            try:
                # Parse based on doc type
                if doc_type == "w2":
                    result = parse_fn(pdf_path, p)
                else:
                    result = parse_fn(pdf_path)
                
                with open(json_path, "w") as f:
                    json.dump(result, f, indent=2)
                
                if verbose:
                    print(f"  ✅ {json_name}")
                total_saved += 1
                
            except Exception as e:
                print(f"  ❌ {pdf_path.name}: {e}")
                total_errors += 1
    
    print(f"\n📊 Summary: {total_saved} saved, {total_errors} errors")
    return total_saved, total_errors


def check_groundtruth(
    doc_type: str,
    get_pdfs_fn,
    get_groundtruth_dir_fn,
    parse_fn,
    person: Optional[str] = None,
    verbose: bool = True
) -> tuple[int, int, list]:
    """
    Compare parsed output against existing groundtruth.
    
    Args:
        doc_type: "paystub" or "w2" (for display)
        get_pdfs_fn: Function to get PDF paths for a person
        get_groundtruth_dir_fn: Function to get groundtruth dir for a person
        parse_fn: Function to parse PDF and return dict
        person: Specific person to check, or None for all
        verbose: Print progress messages
        
    Returns:
        (passed_count, failed_count, failures_list)
    """
    persons = [person] if person else get_all_persons()
    
    total_passed = 0
    total_failed = 0
    failures = []
    
    for p in persons:
        pdfs = get_pdfs_fn(p)
        groundtruth_dir = get_groundtruth_dir_fn(p)
        
        if not groundtruth_dir.exists():
            if verbose:
                print(f"No {doc_type} groundtruth folder for {p}")
            continue
        
        if verbose:
            print(f"\n{'='*60}")
            print(f"Checking {doc_type} for {p}")
            print(f"{'='*60}")
        
        for pdf_path in pdfs:
            json_name = pdf_path.stem + ".json"
            truth_path = groundtruth_dir / json_name
            
            if not truth_path.exists():
                if verbose:
                    print(f"  ⏭️  {pdf_path.name}: No groundtruth (skipped)")
                continue
            
            try:
                # Parse based on doc type
                if doc_type == "w2":
                    result = parse_fn(pdf_path, p)
                else:
                    result = parse_fn(pdf_path)
                
                # Load groundtruth
                with open(truth_path) as f:
                    expected = json.load(f)
                
                # Compare
                diffs = compare_results(result, expected)
                
                if diffs:
                    total_failed += 1
                    failures.append((p, pdf_path.name, diffs))
                    if verbose:
                        print(f"  ❌ {pdf_path.name}:")
                        for diff in diffs[:5]:
                            print(f"      {diff}")
                        if len(diffs) > 5:
                            print(f"      ... and {len(diffs) - 5} more differences")
                else:
                    total_passed += 1
                    if verbose:
                        print(f"  ✅ {pdf_path.name}")
                        
            except Exception as e:
                total_failed += 1
                failures.append((p, pdf_path.name, [f"Error: {e}"]))
                print(f"  ❌ {pdf_path.name}: {e}")
    
    print(f"\n📊 Summary: {total_passed} passed, {total_failed} failed")
    return total_passed, total_failed, failures


def compare_results(actual: dict, expected: dict, tolerance: float = 0.02) -> list[str]:
    """
    Compare two results and return list of differences.
    
    Args:
        actual: Parsed result
        expected: Ground truth
        tolerance: Tolerance for float comparison
        
    Returns:
        List of difference descriptions (empty if match)
    """
    diffs = []
    
    def compare_values(path: str, act, exp):
        """Compare two values, adding to diffs if different."""
        if act is None and exp is None:
            return
        if act is None or exp is None:
            diffs.append(f"{path}: actual={act}, expected={exp}")
            return
        if isinstance(exp, (int, float)) and isinstance(act, (int, float)):
            if abs(act - exp) > tolerance:
                diffs.append(f"{path}: actual={act:.2f}, expected={exp:.2f}")
        elif isinstance(exp, dict) and isinstance(act, dict):
            compare_dicts(path, act, exp)
        elif isinstance(exp, list) and isinstance(act, list):
            if act != exp:
                diffs.append(f"{path}: lists differ")
        elif act != exp:
            diffs.append(f"{path}: actual={act}, expected={exp}")
    
    def compare_dicts(path: str, act: dict, exp: dict):
        """Recursively compare dictionaries."""
        all_keys = set(act.keys()) | set(exp.keys())
        for key in all_keys:
            key_path = f"{path}.{key}" if path else key
            compare_values(key_path, act.get(key), exp.get(key))
    
    compare_dicts("", actual, expected)
    return diffs


# =============================================================================
# Main CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Manage ground truth files for paystub and W-2 parsers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    subparsers = parser.add_subparsers(dest="doc_type", required=True)
    
    # Paystub subcommand
    paystub_parser = subparsers.add_parser("paystub", help="Manage paystub groundtruth")
    paystub_sub = paystub_parser.add_subparsers(dest="command", required=True)
    
    paystub_check = paystub_sub.add_parser("check", help="Check against groundtruth")
    paystub_check.add_argument("--person", "-p", help="Specific person to check")
    paystub_check.add_argument("--quiet", "-q", action="store_true", help="Only show summary")
    
    paystub_save = paystub_sub.add_parser("save", help="Save to groundtruth")
    paystub_save.add_argument("--person", "-p", help="Specific person to save")
    paystub_save.add_argument("--force", "-f", action="store_true", required=True,
                              help="Required flag to confirm overwriting")
    paystub_save.add_argument("--quiet", "-q", action="store_true", help="Only show summary")
    
    # W-2 subcommand
    w2_parser = subparsers.add_parser("w2", help="Manage W-2 groundtruth")
    w2_sub = w2_parser.add_subparsers(dest="command", required=True)
    
    w2_check = w2_sub.add_parser("check", help="Check against groundtruth")
    w2_check.add_argument("--person", "-p", help="Specific person to check")
    w2_check.add_argument("--quiet", "-q", action="store_true", help="Only show summary")
    
    w2_save = w2_sub.add_parser("save", help="Save to groundtruth")
    w2_save.add_argument("--person", "-p", help="Specific person to save")
    w2_save.add_argument("--force", "-f", action="store_true", required=True,
                         help="Required flag to confirm overwriting")
    w2_save.add_argument("--quiet", "-q", action="store_true", help="Only show summary")
    
    args = parser.parse_args()
    
    # Select functions based on doc type
    if args.doc_type == "paystub":
        get_pdfs = get_paystub_pdfs
        get_groundtruth_dir = get_paystub_groundtruth_dir
        parse_fn = parse_paystub_to_dict
    else:  # w2
        get_pdfs = get_w2_pdfs
        get_groundtruth_dir = get_w2_groundtruth_dir
        parse_fn = parse_w2_to_dict
    
    # Execute command
    if args.command == "check":
        passed, failed, _ = check_groundtruth(
            doc_type=args.doc_type,
            get_pdfs_fn=get_pdfs,
            get_groundtruth_dir_fn=get_groundtruth_dir,
            parse_fn=parse_fn,
            person=args.person,
            verbose=not args.quiet
        )
        sys.exit(0 if failed == 0 else 1)
        
    elif args.command == "save":
        saved, errors = save_groundtruth(
            doc_type=args.doc_type,
            get_pdfs_fn=get_pdfs,
            get_groundtruth_dir_fn=get_groundtruth_dir,
            parse_fn=parse_fn,
            person=args.person,
            verbose=not args.quiet
        )
        sys.exit(0 if errors == 0 else 1)


if __name__ == "__main__":
    main()
