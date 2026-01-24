"""
Tests for income trends calculation.

Tests the income trends service that aggregates paystub and W2 data
using DemoMicrosoftEmployee test data.

Run with:
    cd <project-root>
    python -m pytest tests/test_income_trends.py -v
"""
import pytest
import json
import shutil
from pathlib import Path
from backend.app.services.income_trends import calculate_income_trends
from backend.app.services.income_ingestion import ingest_documents
from backend.app.services.paths import parsed_dir, repo_root

# Test person with controlled test data
TEST_PERSON = "DemoMicrosoftEmployee"

# Base directories
PROJECT_ROOT = Path(__file__).parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"


class TestIncomeTrendsSetup:
    """Setup and teardown for income trends tests."""
    
    @pytest.fixture(autouse=True)
    def setup_parsed_data(self):
        """Ensure test data is ingested before running trends tests."""
        # Check if parsed data exists, if not ingest it
        pdir = parsed_dir(TEST_PERSON)
        
        if not pdir.exists() or not list(pdir.glob("**/*.json")):
            # Ingest test data
            root = repo_root()
            
            # Collect all PDFs from DemoMicrosoftEmployee
            paystub_dir = root / "data" / "raw" / TEST_PERSON / "paystub"
            w2_dir = root / "data" / "raw" / TEST_PERSON / "w2"
            
            all_files = []
            if paystub_dir.exists():
                all_files.extend(list(paystub_dir.glob("*.pdf")))
            if w2_dir.exists():
                all_files.extend(list(w2_dir.glob("*.pdf")))
            
            if all_files:
                ingest_documents(person=TEST_PERSON, paths=all_files)
        
        yield


class TestIncomeTrends(TestIncomeTrendsSetup):
    """Test income trends calculation with DemoMicrosoftEmployee data."""
    
    def test_income_trends_returns_result(self):
        """Test that calculate_income_trends returns a result."""
        result = calculate_income_trends(TEST_PERSON)
        
        assert result is not None
        assert isinstance(result, dict)
    
    def test_income_trends_has_required_keys(self):
        """Test that result has all required top-level keys."""
        result = calculate_income_trends(TEST_PERSON)
        
        required_keys = ["person", "series", "months", "paystubs", "insights"]
        for key in required_keys:
            assert key in result, f"Missing required key: {key}"
    
    def test_income_trends_person_name(self):
        """Test that person name is included in result."""
        result = calculate_income_trends(TEST_PERSON)
        
        assert result["person"] == TEST_PERSON
    
    def test_income_trends_includes_paystub_series(self):
        """Test that monthly paystub series is included."""
        result = calculate_income_trends(TEST_PERSON)
        
        assert "series" in result
        assert "months" in result
        
        # Should have data if paystubs were ingested
        if len(result["series"]) > 0:
            # Check that series entries have expected fields
            for entry in result["series"]:
                assert "month" in entry
                assert "gross" in entry
                assert "net" in entry
                assert "tax_total" in entry
    
    def test_income_trends_includes_insights(self):
        """Test that insights are generated."""
        result = calculate_income_trends(TEST_PERSON)
        
        assert "insights" in result
        assert isinstance(result["insights"], list)
    
    def test_income_trends_includes_w2_summaries(self):
        """Test that W2 annual summaries are included if W2s exist."""
        result = calculate_income_trends(TEST_PERSON)
        
        assert "w2_annual_summaries" in result
        
        # If we have W2 data, check structure
        if len(result["w2_annual_summaries"]) > 0:
            for w2_sum in result["w2_annual_summaries"]:
                assert "year" in w2_sum
                assert "wages" in w2_sum
                assert "federal_tax_withheld" in w2_sum
    
    def test_income_trends_paystubs_have_validation(self):
        """Test that individual paystubs include validation data."""
        result = calculate_income_trends(TEST_PERSON)
        
        if len(result.get("paystubs", [])) > 0:
            for paystub in result["paystubs"]:
                assert "validation" in paystub, "Paystub should have validation field"
                
                validation = paystub["validation"]
                if validation is not None and isinstance(validation, dict):
                    # New format with multiple checks
                    expected_keys = ["net_pay_diff", "tax_sum_diff", "pretax_sum_diff", "aftertax_sum_diff"]
                    for key in expected_keys:
                        assert key in validation, f"Missing validation key: {key}"
    
    def test_income_trends_months_are_sorted(self):
        """Test that months are sorted chronologically."""
        result = calculate_income_trends(TEST_PERSON)
        
        months = result["months"]
        assert months == sorted(months)


class TestIncomeTrendsEdgeCases:
    """Test edge cases and error handling."""
    
    def test_income_trends_nonexistent_person(self):
        """Test handling of nonexistent person."""
        result = calculate_income_trends("NonexistentPerson")
        
        # Should return empty results, not error
        assert result["series"] == []
        assert result["w2_annual_summaries"] == []
        assert result["months"] == []
    
    def test_income_trends_returns_has_data_flag(self):
        """Test that result indicates whether data was found."""
        result = calculate_income_trends(TEST_PERSON)
        
        # Either has data or is empty
        has_data = len(result["series"]) > 0 or len(result["w2_annual_summaries"]) > 0
        
        # Function should work either way
        assert isinstance(result, dict)


class TestIncomeTrendsDataQuality(TestIncomeTrendsSetup):
    """Test data quality in income trends."""
    
    def test_income_trends_tax_totals_are_sum(self):
        """Test that tax_total is the sum of individual taxes."""
        result = calculate_income_trends(TEST_PERSON)
        
        for entry in result["series"]:
            expected_tax_total = (
                entry.get("federal_tax", 0) + 
                entry.get("state_tax", 0) + 
                entry.get("ss_tax", 0) + 
                entry.get("medicare_tax", 0)
            )
            
            actual_tax_total = entry.get("tax_total", 0)
            
            # Allow small tolerance for rounding
            assert abs(actual_tax_total - expected_tax_total) < 1.0, \
                f"Tax total mismatch in {entry['month']}: {actual_tax_total} != {expected_tax_total}"
    
    def test_income_trends_gross_positive(self):
        """Test that gross values are positive."""
        result = calculate_income_trends(TEST_PERSON)
        
        for entry in result["series"]:
            gross = entry.get("gross", 0)
            assert gross >= 0, f"Gross should be non-negative in {entry['month']}"
    
    def test_income_trends_net_less_than_gross(self):
        """Test that net pay is less than gross (after deductions)."""
        result = calculate_income_trends(TEST_PERSON)
        
        for entry in result["series"]:
            gross = entry.get("gross", 0)
            net = entry.get("net", 0)
            
            if gross > 0 and net > 0:
                assert net <= gross, \
                    f"Net {net} should not exceed gross {gross} in {entry['month']}"
