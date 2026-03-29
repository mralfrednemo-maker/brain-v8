"""Tests for Bing search — cite-to-URL conversion."""
from thinker.bing_search import _cite_to_url


class TestCiteToUrl:

    def test_standard_cite(self):
        assert _cite_to_url("https://www.example.com › path › page") == "https://www.example.com/path/page"

    def test_cite_without_scheme(self):
        result = _cite_to_url("www.example.com › docs › api")
        assert result == "https://www.example.com/docs/api"

    def test_cite_single_path(self):
        assert _cite_to_url("https://nvd.nist.gov › vuln") == "https://nvd.nist.gov/vuln"

    def test_empty_cite(self):
        assert _cite_to_url("") == ""

    def test_cite_no_separator(self):
        assert _cite_to_url("https://example.com") == "https://example.com"

    def test_cite_with_tight_separator(self):
        """Some cites don't have spaces around ›."""
        assert _cite_to_url("https://example.com›path") == "https://example.com/path"
