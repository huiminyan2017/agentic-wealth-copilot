# Paystub Parser Testing

This directory contains test infrastructure for the Microsoft paystub parser.

## Setup

First, ensure you have the required dependencies installed:

```bash
# From the repository root
pip install pdfplumber
```

Or install all project dependencies:

```bash
pip install -r requirements.txt
```

## Test Script

The `test_paystub_parser.py` script tests the `parse_paystub_msft_simple` function against PDF files.

### Usage

```bash
# From the repository root
python backend/test_paystub_parser.py <pdf_file1> <pdf_file2> ...
```

### Example

```bash
# Test with sample paystub PDFs
python backend/test_paystub_parser.py \
    data/samples/paystub_sample1.pdf \
    data/samples/paystub_sample2.pdf
```

## What the Test Script Does

1. **Parses each PDF** using the `parse_paystub_msft_simple` function
2. **Displays extracted data** in JSON format
3. **Validates critical fields**:
   - pay_date
   - gross_pay
   - net_pay
   - federal_tax
   - ss_tax
   - medicare_tax
4. **Shows warnings** if any parsing issues occurred
5. **Provides a summary** of test results

## Expected Output

For each PDF file, you'll see:
- The parsed data in JSON format
- Validation status for each critical field (✓ or ✗)
- Any warnings from the parser
- Overall pass/fail status

## Adding Test Files

To test the parser:

1. Place your Microsoft paystub PDF files in `data/samples/` directory
2. Run the test script with the file paths
3. Review the parsed output and validation results

**Note:** The parser expects Microsoft paystub PDFs in the format used circa 2025-2026.

## Fixed Issues

- ✓ Added missing `datetime` import in `paystub_parser.py`

## Parser Details

The `parse_paystub_msft_simple` function extracts:

### Current Period Values
- Gross Pay
- Net Pay
- Taxable Wages
- Federal Income Tax
- Social Security Tax
- Medicare Tax
- State Tax

### Year-to-Date (YTD) Values
- YTD Gross
- YTD Taxable Wages
- YTD Federal Tax
- YTD Social Security Tax
- YTD Medicare Tax
- YTD State Tax
- YTD Net Pay

### Additional Info
- Pay Date (in ISO format: YYYY-MM-DD)
- Employer Name (always "microsoft")
- Warnings (any parsing issues)
- Source PDF path
- Parser name
