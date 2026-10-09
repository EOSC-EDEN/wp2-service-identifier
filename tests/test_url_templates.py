import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from unittest.mock import patch
from Identifier import ServiceIdentifier
from tests.test_pipeline import _make_response

# Profiles are injected so the tests do not depend on service_profiles.json contents.
TEMPLATE_PROFILE = {
    "spec_urls": [],
    "probe": {"suffix": "", "method": "GET", "accept": "text/html", "template_value": "water"},
    "validation": {"body_signatures": [{"pattern": "water", "mode": "substring"}]},
    "special": {"skip_html_keyword_checks": True},
}
PLAIN_HTML_PROFILE = {
    "spec_urls": [],
    "probe": {"suffix": "", "method": "GET", "accept": "text/html"},
    "validation": {"body_signatures": []},
    "special": {},
}


def _identifier():
    si = ServiceIdentifier()
    si.profiles = {"TPL": TEMPLATE_PROFILE, "PLAIN": PLAIN_HTML_PROFILE}
    si._api_doc_keywords = ["curl", "getting started"]
    return si


def test_template_profiles_only_for_templated_urls():
    si = _identifier()
    assert si._prefilter_by_url_pattern("https://reactome.org/content/query?q={term}") == ["TPL"]
    assert si._prefilter_by_url_pattern("https://pangaea.de/?q=%7Bsearch_term_string%7D") == ["TPL"]
    assert si._prefilter_by_url_pattern("https://example.com/water") == ["PLAIN"]


def test_templated_url_probed_with_real_query_despite_doc_words():
    si = _identifier()
    seen = []

    def fake_get(url, **kwargs):
        seen.append(url)
        body = "<nav>Getting started</nav>" + ("<h1>Results for water</h1>" if "water" in url else "")
        return _make_response(200, "text/html; charset=utf-8", body, url=url)

    with patch.object(si._session, "get", side_effect=fake_get):
        result = si.identify_url("https://pangaea.de/?q=%7Bsearch_term_string%7D")

    assert result.identified_type == "TPL"
    assert result.confidence == 8.0  # status 3 + MIME 2 + echo signature 3
    assert result.probed_url == "https://pangaea.de/?q=water"
    assert "https://pangaea.de/?q=water" in seen


def test_doc_keyword_needs_word_boundaries():
    si = _identifier()
    assert not si._is_doc_page('<img src="data:image/png;base64,ivborw0kjib6curldxlm">')
    assert si._is_doc_page("call the api with curl -x get")
