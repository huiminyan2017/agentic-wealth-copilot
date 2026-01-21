#!/usr/bin/env python3
"""
Test script for parse_paystub_msft_simple function.

Usage:
    python backend/test_paystub_parser.py <pdf_file1> <pdf_file2> ...

This script tests the parse_paystub_msft_simple function against provided PDF files.
"""

import sys
import json
from pathlib import Path

# Add repository root to path so we can import backend modules
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root))

from backend.app.services.paystub_parser import parse_paystub_msft_simple


def test_paystub_file(pdf_path: Path):
    """Test parsing a single paystub PDF file."""
    print(f"\n{'='*80}")
    print(f"Testing: {pdf_path.name}")
    print(f"{'='*80}")
    
    if not pdf_path.exists():
        print(f"ERROR: File not found: {pdf_path}")
        return False
    
    try:
        result = parse_paystub_msft_simple(pdf_path)
        
        print("\nParsed Results:")
        print("-" * 80)
        print(json.dumps(result, indent=2, default=str))
        
        # Validate critical fields
        print("\n\nValidation:")
        print("-" * 80)
        
        critical_fields = [
            "pay_date",
            "gross_pay",
            "net_pay",
            "federal_tax",
            "ss_tax",
            "medicare_tax",
        ]
        
        missing_fields = []
        for field in critical_fields:
            value = result.get(field)
            status = "✓" if value is not None else "✗"
            print(f"{status} {field}: {value}")
            if value is None:
                missing_fields.append(field)
        
        # Check warnings
        if result.get("warnings"):
            print("\nWarnings:")
            for warning in result["warnings"]:
                print(f"  ⚠ {warning}")
        
        if missing_fields:
            print(f"\n⚠ Warning: Missing {len(missing_fields)} critical field(s): {', '.join(missing_fields)}")
        else:
            print("\n✓ All critical fields extracted successfully!")
        
        return len(missing_fields) == 0
        
    except Exception as e:
        print(f"ERROR: Failed to parse {pdf_path.name}")
        print(f"Exception: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main test function."""
    if len(sys.argv) < 2:
        print("Usage: python backend/test_paystub_parser.py <pdf_file1> <pdf_file2> ...")
        print("\nExample:")
        print("  python backend/test_paystub_parser.py data/samples/paystub1.pdf data/samples/paystub2.pdf")
        sys.exit(1)
    
    pdf_files = [Path(arg) for arg in sys.argv[1:]]
    
    print("Microsoft Paystub Parser Test")
    print("="*80)
    print(f"Testing {len(pdf_files)} file(s)")
    
    results = []
    for pdf_file in pdf_files:
        success = test_paystub_file(pdf_file)
        results.append((pdf_file.name, success))
    
    # Summary
    print("\n\n")
    print("="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    for filename, success in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{status}: {filename}")
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    print(f"\nTotal: {passed}/{total} tests passed")
    
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
