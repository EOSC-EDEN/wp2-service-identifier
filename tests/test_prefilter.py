import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from Identifier import IdentificationResult, CandidateMatch

def test_identification_result_defaults():
    r = IdentificationResult(url="https://example.com")
    assert r.identified_type is None
    assert r.confidence is None
    assert r.ambiguous is False
    assert r.runners_up == []
    assert r.had_redirect is False
    assert r.error is None
    assert r.note is None

def test_candidate_match_fields():
    c = CandidateMatch(service_type="OAI-PMH", score=8.5, matched_mime=True, matched_body_signatures=["<oai-pmh"])
    assert c.service_type == "OAI-PMH"
    assert c.score == 8.5
    assert c.matched_mime is True
    assert c.matched_body_signatures == ["<oai-pmh"]
