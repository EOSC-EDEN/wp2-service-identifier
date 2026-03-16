import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from unittest.mock import MagicMock
from Identifier import ServiceIdentifier


def _make_response(status=200, content_type="text/xml", text=""):
    r = MagicMock()
    r.status_code = status
    r.headers = {"Content-Type": content_type}
    r.text = text
    r.url = "https://example.com"
    r.history = []
    return r


def test_score_perfect_oai_pmh():
    si = ServiceIdentifier()
    resp = _make_response(200, "text/xml", "<OAI-PMH xmlns:oai='...'><Identify/></OAI-PMH>")
    score, matched_mime, matched_sigs = si._score_response(resp, "OAI-PMH")
    # Should get status pts (3) + MIME pts (2) + at least partial body pts
    assert score >= 5.0

def test_score_zero_on_5xx():
    si = ServiceIdentifier()
    resp = _make_response(500, "text/html", "<html>Error</html>")
    score, matched_mime, matched_sigs = si._score_response(resp, "OAI-PMH")
    assert score == 0.0

def test_score_zero_on_4xx():
    si = ServiceIdentifier()
    resp = _make_response(404, "text/html", "<html>Not Found</html>")
    score, matched_mime, matched_sigs = si._score_response(resp, "OAI-PMH")
    assert score == 0.0

def test_score_mime_mismatch_lowers_score():
    si = ServiceIdentifier()
    resp_xml = _make_response(200, "text/xml", "")
    resp_html = _make_response(200, "text/html", "")
    score_xml, _, _ = si._score_response(resp_xml, "OAI-PMH")
    score_html, _, _ = si._score_response(resp_html, "OAI-PMH")
    assert score_xml > score_html

def test_score_mime_match_sets_flag():
    si = ServiceIdentifier()
    resp = _make_response(200, "text/xml", "")
    _, matched_mime, _ = si._score_response(resp, "OAI-PMH")
    assert matched_mime is True

def test_score_body_partial_credit():
    si = ServiceIdentifier()
    oai_profile = si.profiles.get("OAI-PMH", {})
    sigs = oai_profile.get("validation", {}).get("body_signatures", [])
    if len(sigs) >= 2:
        first_pattern = sigs[0]["pattern"]
        resp_partial = _make_response(200, "text/xml", first_pattern)
        score_partial, _, _ = si._score_response(resp_partial, "OAI-PMH")
        all_patterns = " ".join(s["pattern"] for s in sigs)
        resp_full = _make_response(200, "text/xml", all_patterns)
        score_full, _, _ = si._score_response(resp_full, "OAI-PMH")
        assert score_partial <= score_full

def test_score_clamped_to_10():
    si = ServiceIdentifier()
    resp = _make_response(200, "text/xml",
        "<OAI-PMH>http://www.openarchives.org/OAI/2.0/</OAI-PMH>")
    score, _, _ = si._score_response(resp, "OAI-PMH")
    assert score <= 10.0

def test_shortlist_excludes_below_threshold():
    si = ServiceIdentifier()
    resp = _make_response(404, "text/html", "")
    candidates = list(si.profiles.keys())
    shortlist = si._score_against_candidates(resp, candidates)
    # 404 gives 0 status points → no profile should cross the threshold
    assert all(score >= si.low_threshold for _, score, _, _ in shortlist)


from Identifier import CandidateMatch

def test_rank_returns_best_match():
    si = ServiceIdentifier()
    scores = [
        ("OAI-PMH", 8.5, True, ["<oai-pmh"]),
        ("OAI-Static", 4.1, True, ["<oai-pmh"]),
        ("SPARQL", 1.2, False, []),
    ]
    result = si._rank_and_emit("https://example.com", scores)
    assert result.identified_type == "OAI-PMH"
    assert result.confidence == 8.5
    assert result.ambiguous is False

def test_rank_null_result_below_min_confidence():
    si = ServiceIdentifier()
    scores = [("OAI-PMH", 2.0, False, []), ("SPARQL", 1.5, False, [])]
    result = si._rank_and_emit("https://example.com", scores)
    assert result.identified_type is None
    assert result.note is not None

def test_rank_ambiguous_when_top_two_close():
    si = ServiceIdentifier()
    scores = [
        ("SPARQL", 6.2, True, []),
        ("OGC-CSW", 5.8, False, []),
    ]
    result = si._rank_and_emit("https://example.com", scores)
    assert result.ambiguous is True
    assert result.identified_type == "SPARQL"  # still returns best guess

def test_rank_runners_up_capped():
    si = ServiceIdentifier(max_runners_up=2)
    scores = [
        ("OAI-PMH", 8.0, True, []),
        ("SPARQL", 5.0, False, []),
        ("REST", 4.0, False, []),
        ("OGC-WMS", 3.5, False, []),
    ]
    result = si._rank_and_emit("https://example.com", scores)
    assert len(result.runners_up) == 2

def test_rank_runners_up_have_correct_matched_mime():
    si = ServiceIdentifier()
    scores = [
        ("OAI-PMH", 8.0, True, ["<oai-pmh"]),
        ("SPARQL", 5.0, False, []),
    ]
    result = si._rank_and_emit("https://example.com", scores)
    assert result.runners_up[0].service_type == "SPARQL"
    assert result.runners_up[0].matched_mime is False

def test_rank_empty_scores_returns_null():
    si = ServiceIdentifier()
    result = si._rank_and_emit("https://example.com", [])
    assert result.identified_type is None
