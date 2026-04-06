"""Tests for Brave search — error types."""
from brain.brave_search import SearchError


class TestSearchError:

    def test_is_exception(self):
        err = SearchError("Brave search failed")
        assert isinstance(err, Exception)
        assert str(err) == "Brave search failed"

    def test_inherits_from_exception(self):
        assert issubclass(SearchError, Exception)

    def test_can_be_caught(self):
        try:
            raise SearchError("test error")
        except SearchError as e:
            assert "test error" in str(e)
