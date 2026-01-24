"""
Tests for income scan endpoint.

Tests the scan_income endpoint that detects available documents:
1. Scanning for W2 and paystub PDFs
2. Document kind detection
3. Employer detection
4. SHA256 calculation
5. Error handling

Uses DemoMicrosoftEmployee folder with known test files and groundtruth.

Run with:
    cd <project-root>
    python -m pytest tests/test_income_scan.py -v
"""
import pytest
from pathlib import Path
from fastapi import HTTPException

from backend.app.routes.income import scan_income
from backend.app.services.paths import repo_root

# Test person - uses controlled test data
TEST_PERSON = "DemoMicrosoftEmployee"

# Expected test data:
# data/raw/TEST_PERSON/
#   paystub/test paystub pdf
#   w2/test w2 pdf
# Corresponding groundtruth files(test label files):
# data/raw/TEST_PERSON/
#   paystub_groundtruth/*.json
#   w2_groundtruth/*.json

class TestIncomeScan:
    """Test income scan functionality."""
    
    def test_scan_income_finds_files(self):
        """Test that scan finds existing files for DemoMicrosoftEmployee."""
        response = scan_income(TEST_PERSON)
        
        assert response.items is not None
        assert len(response.items) > 0
    
    def test_scan_income_has_required_fields(self):
        """Test that scan results have all required fields."""
        response = scan_income(TEST_PERSON)
        
        for item in response.items:
            assert item.person == TEST_PERSON
            assert item.kind in ["w2", "paystub", "unknown"]
            assert item.employer is not None
            assert item.rel_path is not None
            assert item.sha256 is not None
            assert len(item.sha256) == 64  # SHA256 is 64 hex chars
    
    def test_scan_income_detects_w2_from_filename(self):
        """Test that W2 files are correctly identified."""
        response = scan_income(TEST_PERSON)
        
        w2_items = [item for item in response.items if item.kind == "w2"]
        assert len(w2_items) >= 1  # DemoMicrosoftEmployee has at least 1 W2
        
        # Check that all W2 files have w2 in the path
        for item in w2_items:
            assert "w2" in item.rel_path.lower() or "w-2" in item.rel_path.lower()
    
    def test_scan_income_detects_paystub_from_filename(self):
        """Test that paystub files are correctly identified."""
        response = scan_income(TEST_PERSON)
        
        paystub_items = [item for item in response.items if item.kind == "paystub"]
        assert len(paystub_items) >= 2  # DemoMicrosoftEmployee has 2 paystubs
        
        # Check that paystub files have relevant keywords
        for item in paystub_items:
            path_lower = item.rel_path.lower()
            assert any(keyword in path_lower for keyword in ["pay", "stub", "paystub"])
    
    def test_scan_income_detects_microsoft_employer(self):
        """Test that Microsoft employer is correctly detected."""
        response = scan_income(TEST_PERSON)
        
        microsoft_items = [item for item in response.items if item.employer == "microsoft"]
        assert len(microsoft_items) >= 2  # At least 1 W2 + 1 paystub from Microsoft
        
        # Check that Microsoft files have "microsoft" or "msft" in filename
        for item in microsoft_items:
            path_lower = item.rel_path.lower()
            assert "microsoft" in path_lower or "msft" in path_lower
    
    def test_scan_income_rel_paths_are_relative(self):
        """Test that rel_paths are relative to repo root."""
        response = scan_income(TEST_PERSON)
        
        for item in response.items:
            # Relative paths should start with data/raw/
            assert item.rel_path.startswith("data/raw/")
            # Should not be absolute paths
            assert not item.rel_path.startswith("/")
    
    def test_scan_income_sha256_is_consistent(self):
        """Test that SHA256 hashes are consistent for same file."""
        response1 = scan_income(TEST_PERSON)
        response2 = scan_income(TEST_PERSON)
        
        # Create dict of path -> sha256 for both responses
        hashes1 = {item.rel_path: item.sha256 for item in response1.items}
        hashes2 = {item.rel_path: item.sha256 for item in response2.items}
        
        # Same files should have same hashes
        for path in hashes1:
            if path in hashes2:
                assert hashes1[path] == hashes2[path], f"SHA256 mismatch for {path}"
    
    def test_scan_income_nonexistent_person_raises_404(self):
        """Test that scanning nonexistent person raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            scan_income("NonexistentPerson")
        
        assert exc_info.value.status_code == 404
        assert "Missing folder" in exc_info.value.detail
    
    def test_scan_income_only_includes_pdfs(self):
        """Test that scan only includes PDF files."""
        response = scan_income(TEST_PERSON)
        
        for item in response.items:
            assert item.rel_path.lower().endswith(".pdf")
    
    def test_scan_income_file_counts(self):
        """Test that we find the expected number of files for DemoMicrosoftEmployee."""
        response = scan_income(TEST_PERSON)
        
        w2_items = [item for item in response.items if item.kind == "w2"]
        paystub_items = [item for item in response.items if item.kind == "paystub"]
        
        # DemoMicrosoftEmployee has 1 W2 and 2 paystubs
        assert len(w2_items) == 1, f"Expected 1 W2, got {len(w2_items)}"
        assert len(paystub_items) == 2, f"Expected 2 paystubs, got {len(paystub_items)}"


class TestIncomeScanPaths:
    """Test path handling in income scan."""
    
    def test_scan_income_paths_exist(self):
        """Test that all scanned files actually exist."""
        response = scan_income(TEST_PERSON)
        root = repo_root()
        
        for item in response.items:
            file_path = root / item.rel_path
            assert file_path.exists(), f"File should exist: {file_path}"
            assert file_path.is_file(), f"Should be a file: {file_path}"
    
    def test_scan_income_checks_both_w2_and_paystub_dirs(self):
        """Test that scan checks both w2 and paystub subdirectories."""
        response = scan_income(TEST_PERSON)
        
        # Should have items from both directories
        w2_items = [item for item in response.items if "/w2/" in item.rel_path]
        paystub_items = [item for item in response.items if "/paystub/" in item.rel_path]
        
        assert len(w2_items) > 0, "Should have W2 files"
        assert len(paystub_items) > 0, "Should have paystub files"


class TestGroundtruthExists:
    """Test that groundtruth files exist for test data."""
    
    def test_paystub_groundtruth_exists(self):
        """Test that paystub groundtruth files exist."""
        root = repo_root()
        gt_dir = root / "data" / "raw" / TEST_PERSON / "paystub_groundtruth"
        
        assert gt_dir.exists(), f"Groundtruth directory should exist: {gt_dir}"
        
        gt_files = list(gt_dir.glob("*.json"))
        assert len(gt_files) >= 1, "Should have at least 1 paystub groundtruth file"
    
    def test_w2_groundtruth_exists(self):
        """Test that W2 groundtruth files exist."""
        root = repo_root()
        gt_dir = root / "data" / "raw" / TEST_PERSON / "w2_groundtruth"
        
        assert gt_dir.exists(), f"Groundtruth directory should exist: {gt_dir}"
        
        gt_files = list(gt_dir.glob("*.json"))
        assert len(gt_files) >= 1, "Should have at least 1 W2 groundtruth file"
