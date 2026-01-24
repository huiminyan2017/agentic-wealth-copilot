"""
Tests for w2_parser.py and ingestion pipeline.

Discovers all Demo* users under data/raw/ automatically and tests each one.
Also covers document detection and end-to-end ingestion: JSON creation, index, deduplication.

Run with:
    cd <project-root>
    python -m pytest "tests/test_w2_ingest_&_parse.py" -v
"""
import json
import shutil
from pathlib import Path
import pytest
from backend.app.services.w2_parser import parse_w2
from backend.app.services.income_ingestion import ingest_documents, detect_doc_kind, detect_employer
from backend.app.services.paths import parsed_dir, repo_root
from backend.app.constants import EMPLOYER_MICROSOFT

PROJECT_ROOT = Path(__file__).parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
TEMP_TEST_PERSON = "TestW2Temp"

# IRS Social Security wage base limits (26 U.S.C. § 3121).
# Employers must stop withholding SS tax once wages exceed this cap, so W-2
# Box 3 (SS wages) can never legally exceed it — even when Box 1 wages are far
# higher (e.g. DemoMicrosoftEmployee: $862k wages but only $128,400 SS wages,
# the 2018 cap).  The SSA announces the new limit each October for the
# following year.
_SS_LIMITS = {2018: 128400, 2019: 132900, 2020: 137700, 2021: 142800,
              2022: 147000, 2023: 160200, 2024: 168600, 2025: 176100}

# Keys excluded from groundtruth comparison.
# _disclaimer: added by the generate script as a synthetic-data notice; not returned by the parser.
#   (source_pdf_relpath / extracted_text_path / notes are already stripped from W2 groundtruth
#    by the generate script, so they never appear in `expected` and need no special handling.)
_SKIP_KEYS = {"_disclaimer"}


# ---------------------------------------------------------------------------
# Deep comparison helper
# ---------------------------------------------------------------------------

def _assert_json_match(actual, expected, *, tol=0.01, path=""):
    """
    Recursively compare two JSON-like structures.
    - dicts: every key in `expected` (not in _SKIP_KEYS) must match
    - lists: same length, element-wise match
    - floats: abs difference < tol
    - everything else: equality
    """
    if isinstance(expected, dict):
        for key, exp_val in expected.items():
            if key in _SKIP_KEYS:
                continue
            assert key in actual, f"[{path}] Missing key '{key}'"
            _assert_json_match(actual[key], exp_val, tol=tol,
                               path=f"{path}.{key}" if path else key)
    elif isinstance(expected, list):
        assert len(actual) == len(expected), \
            f"[{path}] List length: expected {len(expected)}, got {len(actual)}"
        for i, (a, e) in enumerate(zip(actual, expected)):
            _assert_json_match(a, e, tol=tol, path=f"{path}[{i}]")
    elif isinstance(expected, float):
        assert isinstance(actual, (int, float)), \
            f"[{path}] Expected float, got {type(actual).__name__} ({actual!r})"
        assert abs(float(actual) - expected) < tol, \
            f"[{path}]: expected {expected}, got {actual}"
    else:
        assert actual == expected, \
            f"[{path}]: expected {expected!r}, got {actual!r}"


# ---------------------------------------------------------------------------
# Discovery helpers
# ---------------------------------------------------------------------------

def _discover_w2_cases():
    cases = []
    for user_dir in sorted(RAW_DIR.glob("Demo*")):
        truth_dir = user_dir / "w2_groundtruth"
        pdf_dir   = user_dir / "w2"
        if not truth_dir.exists():
            continue
        for truth_file in sorted(truth_dir.glob("*.json")):
            pdf_path = pdf_dir / (truth_file.stem + ".pdf")
            if not pdf_path.exists():
                continue
            # Read employer from groundtruth — same value used when it was generated
            with open(truth_file) as f:
                employer = json.load(f)["employer_name"]
            cases.append((pdf_path, truth_file, employer,
                           f"{user_dir.name}/{truth_file.stem}"))
    return cases


def _first_demo_w2():
    for user_dir in sorted(RAW_DIR.glob("Demo*")):
        pdfs = sorted((user_dir / "w2").glob("*.pdf")) if (user_dir / "w2").exists() else []
        if pdfs:
            return pdfs[0]
    return None


W2_TEST_CASES = _discover_w2_cases()
_IDS = [tc[3] for tc in W2_TEST_CASES]


# ---------------------------------------------------------------------------
# Groundtruth tests  (parametrized over all Demo* users)
# ---------------------------------------------------------------------------

class TestW2ParserGroundtruth:
    """Parsed output must match the entire groundtruth JSON for every Demo* user."""

    @pytest.mark.parametrize("pdf_path,truth_path,employer,test_id", W2_TEST_CASES, ids=_IDS or None)
    def test_matches_groundtruth(self, pdf_path, truth_path, employer, test_id):
        with open(truth_path) as f:
            expected = json.load(f)

        result = parse_w2(pdf_path, employer, person="TestUser", sha8="test1234")
        actual = result.model_dump(mode="json")

        _assert_json_match(actual, expected, path=test_id)


# ---------------------------------------------------------------------------
# Validation tests  (parametrized)
# ---------------------------------------------------------------------------

class TestW2ParserValidation:
    """Domain-level sanity checks on parsed W2 values."""

    @pytest.mark.parametrize("pdf_path,truth_path,employer,test_id", W2_TEST_CASES, ids=_IDS or None)
    def test_federal_tax_reasonable(self, pdf_path, truth_path, employer, test_id):
        result = parse_w2(pdf_path, employer, "TestUser", "test")
        if result.wages and result.federal_tax_withheld:
            assert result.federal_tax_withheld < result.wages, \
                f"[{test_id}] Federal tax {result.federal_tax_withheld} exceeds wages {result.wages}"
            rate = result.federal_tax_withheld / result.wages
            assert 0.05 < rate < 0.50, \
                f"[{test_id}] Federal tax rate {rate:.1%} seems unreasonable"

    @pytest.mark.parametrize("pdf_path,truth_path,employer,test_id", W2_TEST_CASES, ids=_IDS or None)
    def test_ss_wages_within_limit(self, pdf_path, truth_path, employer, test_id):
        result = parse_w2(pdf_path, employer, "TestUser", "test")
        if result.year in _SS_LIMITS and result.ss_wages is not None:
            limit = _SS_LIMITS[result.year]
            assert result.ss_wages <= limit + 1000, \
                f"[{test_id}] Year {result.year}: SS wages {result.ss_wages} exceeds limit {limit}"


# ---------------------------------------------------------------------------
# Document detection tests
# ---------------------------------------------------------------------------

class TestW2Detection:
    """detect_doc_kind and detect_employer must classify filenames correctly."""

    def test_detect_w2_from_filename(self):
        assert detect_doc_kind("Microsoft-W2-2024.pdf") == "w2"
        assert detect_doc_kind("W-2-Form-2023.pdf") == "w2"
        assert detect_doc_kind("w2_2022.pdf") == "w2"
        assert detect_doc_kind("Test-W2-Microsoft-2024.pdf") == "w2"

    def test_detect_paystub_from_filename(self):
        assert detect_doc_kind("Test-PayStub-Microsoft-2025-12-05.pdf") == "paystub"
        assert detect_doc_kind("paystub_2024-01-15.pdf") == "paystub"

    def test_detect_employer_microsoft(self):
        assert detect_employer("Microsoft-W2-2024.pdf") == EMPLOYER_MICROSOFT
        assert detect_employer("msft-w2-2023.pdf") == EMPLOYER_MICROSOFT
        assert detect_employer("Test-W2-Microsoft-2024.pdf") == EMPLOYER_MICROSOFT


# ---------------------------------------------------------------------------
# Ingestion pipeline tests  (use TEMP_TEST_PERSON to stay isolated)
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_person():
    pdir = parsed_dir(TEMP_TEST_PERSON)
    if pdir.exists():
        shutil.rmtree(pdir)
    yield
    if pdir.exists():
        shutil.rmtree(pdir)


class TestIngestionPipeline:
    """End-to-end W2 ingestion: file creation, index, deduplication."""

    def test_creates_json_and_index(self, temp_person):
        pdf = _first_demo_w2()
        if pdf is None:
            pytest.skip("No Demo* W2 PDF found")

        result = ingest_documents(person=TEMP_TEST_PERSON, paths=[pdf])
        assert result["ingested"] == 1
        assert result["skipped"]  == 0

        pdir = parsed_dir(TEMP_TEST_PERSON)
        assert pdir.exists() and (pdir / "w2").exists()

        json_files = list((pdir / "w2").glob("*.json"))
        assert len(json_files) == 1

        with open(json_files[0]) as f:
            data = json.load(f)
        for field in ["year", "employer_name", "wages", "federal_tax_withheld"]:
            assert field in data, f"Missing field in parsed JSON: {field}"

        index_path = pdir / "index.json"
        assert index_path.exists()
        with open(index_path) as f:
            index = json.load(f)
        assert len(index["files"]) == 1
        rec = list(index["files"].values())[0]
        assert rec["kind"] == "w2"
        assert "employer" in rec

    def test_duplicate_skipped(self, temp_person):
        pdf = _first_demo_w2()
        if pdf is None:
            pytest.skip("No Demo* W2 PDF found")

        r1 = ingest_documents(person=TEMP_TEST_PERSON, paths=[pdf])
        assert r1["ingested"] == 1 and r1["skipped"] == 0

        r2 = ingest_documents(person=TEMP_TEST_PERSON, paths=[pdf])
        assert r2["ingested"] == 0
        assert r2["skipped"]  == 1
        assert r2["skip_reasons"].get("already_ingested") == 1
