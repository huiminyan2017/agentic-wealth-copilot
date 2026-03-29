"""
Tests for paystub_parser.py and ingestion pipeline.

Discovers all Demo* users under data/raw/ automatically and tests each one.
Also covers end-to-end ingestion: JSON creation, index, deduplication, filename format.

Run with:
    cd <project-root>
    python -m pytest "tests/test_paystub_ingest_&_parse.py" -v
"""
import json
import shutil
from pathlib import Path
import pytest
from backend.app.services.paystub_parser import parse_paystub
from backend.app.services.income_ingestion import ingest_documents
from backend.app.services.paths import parsed_dir, repo_root

PROJECT_ROOT = Path(__file__).parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
TEMP_TEST_PERSON = "TestPaystubTemp"

# Keys excluded from groundtruth comparison.
# _disclaimer: added by the generate script as a synthetic-data notice; not returned by the parser.
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

def _discover_paystub_cases():
    cases = []
    for user_dir in sorted(RAW_DIR.glob("Demo*")):
        truth_dir = user_dir / "paystub_groundtruth"
        pdf_dir   = user_dir / "paystub"
        if not truth_dir.exists():
            continue
        for truth_file in sorted(truth_dir.glob("*.json")):
            pdf_path = pdf_dir / (truth_file.stem + ".pdf")
            if pdf_path.exists():
                cases.append((pdf_path, truth_file, f"{user_dir.name}/{truth_file.stem}"))
    return cases


def _first_demo_paystub():
    for user_dir in sorted(RAW_DIR.glob("Demo*")):
        pdfs = sorted((user_dir / "paystub").glob("*.pdf")) if (user_dir / "paystub").exists() else []
        if pdfs:
            return pdfs[0]
    return None


PAYSTUB_TEST_CASES = _discover_paystub_cases()
_IDS = [tc[2] for tc in PAYSTUB_TEST_CASES]


# ---------------------------------------------------------------------------
# Groundtruth tests  (parametrized over all Demo* users)
# ---------------------------------------------------------------------------

class TestParserGroundtruth:
    """Parsed output must match the entire groundtruth JSON for every Demo* user."""

    @pytest.mark.parametrize("pdf_path,truth_path,test_id", PAYSTUB_TEST_CASES, ids=_IDS or None)
    def test_matches_groundtruth(self, pdf_path, truth_path, test_id):
        with open(truth_path) as f:
            expected = json.load(f)

        actual = parse_paystub(pdf_path)

        _assert_json_match(actual, expected, path=test_id)



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
    """End-to-end ingestion: file creation, index, dedup, filename format."""

    def test_creates_json_and_index(self, temp_person):
        pdf = _first_demo_paystub()
        if pdf is None:
            pytest.skip("No Demo* paystub PDF found")

        result = ingest_documents(person=TEMP_TEST_PERSON, paths=[pdf])

        assert result["ingested"] == 1, f"Expected 1 ingested, got {result['ingested']}"
        assert result["skipped"]  == 0, f"Unexpected skips: {result.get('skipped_files', [])}"

        pdir = parsed_dir(TEMP_TEST_PERSON)
        assert pdir.exists()
        assert (pdir / "paystub").exists()

        json_files = list((pdir / "paystub").glob("*.json"))
        assert len(json_files) == 1, f"Expected 1 JSON file, got {len(json_files)}"

        with open(json_files[0]) as f:
            data = json.load(f)
        for field in ["pay_date", "employer_name", "gross", "taxes", "net_pay"]:
            assert field in data, f"Missing field in parsed JSON: {field}"

        index_path = pdir / "income_file_index.json"
        assert index_path.exists(), "income_file_index.json not created"
        with open(index_path) as f:
            index = json.load(f)
        assert "files" in index
        assert len(index["files"]) == 1
        assert list(index["files"].values())[0]["kind"] == "paystub"

    def test_json_filename_format(self, temp_person):
        """JSON filename must be YYYY-MM-DD_<8hexchars>.json."""
        pdf = _first_demo_paystub()
        if pdf is None:
            pytest.skip("No Demo* paystub PDF found")

        ingest_documents(person=TEMP_TEST_PERSON, paths=[pdf])

        json_files = list((parsed_dir(TEMP_TEST_PERSON) / "paystub").glob("*.json"))
        assert len(json_files) == 1

        stem  = json_files[0].stem
        parts = stem.split("_")
        assert len(parts) == 2, f"Expected YYYY-MM-DD_hash, got '{stem}'"

        year, month, day = parts[0].split("-")
        assert len(year) == 4 and year.isdigit()
        assert 1 <= int(month) <= 12
        assert 1 <= int(day)   <= 31

        sha8 = parts[1]
        assert len(sha8) == 8
        assert all(c in "0123456789abcdef" for c in sha8)

    def test_duplicate_skipped(self, temp_person):
        pdf = _first_demo_paystub()
        if pdf is None:
            pytest.skip("No Demo* paystub PDF found")

        r1 = ingest_documents(person=TEMP_TEST_PERSON, paths=[pdf])
        assert r1["ingested"] == 1 and r1["skipped"] == 0

        r2 = ingest_documents(person=TEMP_TEST_PERSON, paths=[pdf])
        assert r2["ingested"] == 0
        assert r2["skipped"]  == 1
        assert r2["skip_reasons"].get("already_ingested") == 1
