"""Tests for Sonar search — basic structure and shared error type."""
from brain.brave_search import SearchError


class TestSonarSearchError:

    def test_uses_search_error(self):
        """Sonar search uses the shared SearchError from brave_search."""
        err = SearchError("Sonar search timed out")
        assert "timed out" in str(err)

    def test_sonar_module_importable(self):
        """Sonar search module should import without errors."""
        import brain.sonar_search  # noqa
        assert hasattr(thinker.sonar_search, "sonar_search")
