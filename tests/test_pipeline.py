import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import requests
from unittest.mock import patch, MagicMock
from Identifier import ServiceIdentifier, IdentificationResult


def _make_response(status=200, content_type="text/xml", text="<hello/>", url="https://example.com"):
    """Helper: build a mock requests.Response."""
    r = MagicMock()
    r.status_code = status
    r.headers = {"Content-Type": content_type}
    r.text = text
    r.content = text.encode()
    r.url = url
    r.history = []
    return r


def test_initial_probe_returns_none_on_connection_error():
    si = ServiceIdentifier()
    with patch.object(si._session, "get", side_effect=requests.exceptions.ConnectionError("refused")):
        result = si._probe("https://unreachable.example.com", suffix=None)
    assert result is None


def test_initial_probe_returns_response_on_success():
    si = ServiceIdentifier()
    mock_resp = _make_response(200, "text/xml", "<oai-pmh/>")
    with patch.object(si._session, "get", return_value=mock_resp):
        result = si._probe("https://example.com/oai", suffix=None)
    assert result is not None
    assert result.status_code == 200


def test_initial_probe_appends_suffix():
    si = ServiceIdentifier()
    mock_resp = _make_response(200, "text/xml", "<oai-pmh/>")
    captured = {}
    def fake_get(url, **kwargs):
        captured["url"] = url
        return mock_resp
    with patch.object(si._session, "get", side_effect=fake_get):
        si._probe("https://example.com/oai", suffix="?verb=Identify")
    assert captured["url"] == "https://example.com/oai?verb=Identify"


def test_targeted_probes_returns_per_profile_scores():
    si = ServiceIdentifier()
    shortlist = [
        ("OAI-PMH", 2.5, True, []),
        ("SPARQL", 1.5, False, []),
    ]
    oai_resp = _make_response(200, "text/xml", "<OAI-PMH><Identify/></OAI-PMH>")
    sparql_resp = _make_response(200, "application/sparql-results+xml", "<sparql/>")

    def fake_get(url, **kwargs):
        if "verb=Identify" in url:
            return oai_resp
        return sparql_resp

    with patch.object(si._session, "get", side_effect=fake_get):
        results = si._run_targeted_probes("https://example.com", shortlist)

    assert isinstance(results, list)
    assert len(results) == 2
    keys = [r[0] for r in results]
    assert "OAI-PMH" in keys
    assert "SPARQL" in keys


def test_targeted_probes_tolerates_timeout():
    """A timed-out probe scores 0.0 and does not crash the run."""
    si = ServiceIdentifier()
    shortlist = [("OAI-PMH", 2.0, False, []), ("SPARQL", 2.0, False, [])]

    def fake_get(url, **kwargs):
        if "verb=Identify" in url:
            raise requests.exceptions.Timeout("timed out")
        return _make_response(200, "application/sparql-results+xml", "<sparql/>")

    with patch.object(si._session, "get", side_effect=fake_get):
        results = si._run_targeted_probes("https://example.com", shortlist)

    keys = [r[0] for r in results]
    # SPARQL result present
    assert "SPARQL" in keys
    # OAI-PMH timed out → score must be 0.0 (not the shortlist score 2.0)
    oai_result = next((r for r in results if r[0] == "OAI-PMH"), None)
    assert oai_result is not None
    assert oai_result[1] == 0.0
