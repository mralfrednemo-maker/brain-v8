"""Tests for Bing search — HTML parsing, redirect resolution."""
from thinker.bing_search import _resolve_bing_redirect


class TestResolveBingRedirect:

    def test_extracts_real_url(self):
        redirect = "https://www.bing.com/ck/a?!&&p=abc&u=a1https%3A%2F%2Fexample.com%2Fpage&ntb=1"
        assert _resolve_bing_redirect(redirect) == "https://example.com/page"

    def test_non_redirect_unchanged(self):
        url = "https://example.com/page"
        assert _resolve_bing_redirect(url) == url

    def test_malformed_redirect_returns_original(self):
        url = "https://www.bing.com/ck/a?broken"
        assert _resolve_bing_redirect(url) == url

    def test_double_encoded_url(self):
        redirect = "https://www.bing.com/ck/a?u=a1https%3A%2F%2Fnvd.nist.gov%2Fvuln%2Fdetail%2FCVE-2026-1234&ntb=1"
        result = _resolve_bing_redirect(redirect)
        assert "nvd.nist.gov" in result

    def test_non_bing_url_passthrough(self):
        url = "https://google.com/search?q=test"
        assert _resolve_bing_redirect(url) == url
