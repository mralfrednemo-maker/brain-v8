"""Tests for full page content fetch."""
import pytest

from thinker.page_fetch import strip_html, truncate_content


class TestStripHtml:

    def test_strips_tags(self):
        assert strip_html("<p>Hello <b>world</b></p>") == "Hello world"

    def test_strips_script_and_style(self):
        html = "<html><head><style>body{}</style></head><body><script>alert(1)</script><p>Content</p></body></html>"
        result = strip_html(html)
        assert "Content" in result
        assert "alert" not in result
        assert "body{}" not in result

    def test_preserves_text(self):
        assert strip_html("plain text") == "plain text"

    def test_decodes_entities(self):
        result = strip_html("&amp; &lt; &gt;")
        assert "&" in result
        assert "<" in result
        assert ">" in result

    def test_collapses_whitespace(self):
        result = strip_html("<p>  lots   of   space  </p>")
        assert result == "lots of space"

    def test_empty_input(self):
        assert strip_html("") == ""

    def test_nested_tags(self):
        html = "<div><ul><li>Item <strong>one</strong></li><li>Item two</li></ul></div>"
        result = strip_html(html)
        assert "Item one" in result
        assert "Item two" in result


class TestTruncateContent:

    def test_under_limit_unchanged(self):
        text = "short text"
        assert truncate_content(text, max_chars=100) == text

    def test_over_limit_truncated(self):
        text = "a" * 200
        result = truncate_content(text, max_chars=100)
        assert len(result) == 100

    def test_default_limit(self):
        text = "a" * 60000
        result = truncate_content(text)
        assert len(result) == 50000

    def test_exact_limit(self):
        text = "a" * 100
        assert truncate_content(text, max_chars=100) == text
