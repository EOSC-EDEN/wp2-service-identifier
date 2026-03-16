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
