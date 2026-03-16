import sys, os, csv, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from unittest.mock import patch
from Identifier import ServiceIdentifier, IdentificationResult


def _make_result(identified_type="OAI-PMH", confidence=8.5):
    return IdentificationResult(
        url="https://example.com/oai",
        identified_type=identified_type,
        confidence=confidence,
    )


def test_batch_csv_round_trip():
    """Write a CSV with endpoints, run batch, check output CSV has identification columns."""
    from batch_identifier import run_csv_batch

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["endpoint", "serviceTitle", "repoTitle"])
        writer.writeheader()
        writer.writerow({
            "endpoint": "https://example.com/oai",
            "serviceTitle": "Test OAI",
            "repoTitle": "Test Repo"
        })
        input_path = f.name

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="") as f:
        output_path = f.name

    with patch.object(ServiceIdentifier, "identify_url", return_value=_make_result()):
        run_csv_batch(input_path, output_path)

    with open(output_path, newline="") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 1
    assert rows[0]["identified_type"] == "OAI-PMH"
    assert rows[0]["confidence"] == "8.5"
    assert "ambiguous" in rows[0]
    assert "runners_up" in rows[0]

    os.unlink(input_path)
    os.unlink(output_path)


def test_batch_csv_skips_empty_endpoint():
    """Rows with no endpoint URL are skipped without error."""
    from batch_identifier import run_csv_batch

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["endpoint"])
        writer.writeheader()
        writer.writerow({"endpoint": ""})
        input_path = f.name

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="") as f:
        output_path = f.name

    with patch.object(ServiceIdentifier, "identify_url", return_value=_make_result()) as mock_id:
        run_csv_batch(input_path, output_path)

    mock_id.assert_not_called()

    with open(output_path, newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 0

    os.unlink(input_path)
    os.unlink(output_path)
