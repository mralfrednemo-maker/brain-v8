"""Tests for the search system."""
import pytest
from unittest.mock import AsyncMock, patch

from brain.search import SearchOrchestrator, SearchPhase, parse_model_search_requests
from brain.types import EvidenceItem, Confidence


class TestParseModelSearchRequests:
    """parse_model_search_requests extracts queries from model output appendices."""

    def test_numbered_queries(self):
        output = (
            "Some analysis text...\n\n"
            "SEARCH_REQUESTS:\n"
            "1. CVE-2026-1234 JWT bypass severity CVSS score\n"
            "2. GDPR Article 33 notification timeline requirements\n"
            "3. SOC 2 breach reporting obligations\n"
        )
        queries = parse_model_search_requests(output)
        assert len(queries) == 3
        assert "CVE-2026-1234" in queries[0]
        assert "GDPR" in queries[1]

    def test_none_returns_empty(self):
        output = "Some analysis...\n\nSEARCH_REQUESTS:\nNONE\n"
        queries = parse_model_search_requests(output)
        assert queries == []

    def test_no_section_returns_empty(self):
        output = "Just analysis text, no search requests section."
        queries = parse_model_search_requests(output)
        assert queries == []

    def test_max_5_queries(self):
        lines = [f"{i}. Query number {i}" for i in range(1, 10)]
        output = "Analysis...\n\nSEARCH_REQUESTS:\n" + "\n".join(lines)
        queries = parse_model_search_requests(output)
        assert len(queries) == 5


class TestSearchOrchestrator:
    """Search orchestration: model-requested + proactive queries."""

    def test_collect_model_requests(self, mock_llm):
        """collect_model_requests parses search appendices directly — no LLM call."""
        orch = SearchOrchestrator(mock_llm, search_fn=AsyncMock(return_value=[]), max_results=10)
        model_outputs = {
            "r1": "Analysis...\n\nSEARCH_REQUESTS:\n1. CVE-2026-1234 details\n2. JWT bypass mitigations\n",
            "glm5": "Analysis...\n\nSEARCH_REQUESTS:\n1. GDPR Article 33 timeline\n",
            "kimi": "Analysis...\n\nSEARCH_REQUESTS:\nNONE\n",
        }
        queries = orch.collect_model_requests(model_outputs)
        assert len(queries) == 3
        assert "CVE-2026-1234" in queries[0]

    async def test_proactive_queries_from_claims(self, mock_llm):
        mock_llm.add_response("sonnet", (
            "QUERIES:\n"
            "1. GDPR Article 33 breach notification deadline hours\n"
        ))
        orch = SearchOrchestrator(mock_llm, search_fn=AsyncMock(return_value=[]), max_results=10)
        queries = await orch.generate_proactive_queries(
            {
                "r1": "The 847 requests over 33 minutes suggest automated exploitation",
                "kimi": "GDPR requires notification within 72 hours",
            },
            already_queued=["CVE-2026-1234 details"],
        )
        assert len(queries) >= 1

    async def test_proactive_receives_already_queued(self, mock_llm):
        """Proactive prompt includes already_queued so it doesn't duplicate model requests."""
        mock_llm.add_response("sonnet", "NONE\n")
        orch = SearchOrchestrator(mock_llm, search_fn=AsyncMock(return_value=[]), max_results=10)
        await orch.generate_proactive_queries(
            {"r1": "text"},
            already_queued=["CVE-2026-1234 details", "GDPR timeline"],
        )
        prompt = mock_llm.last_prompt_for("sonnet")
        assert "CVE-2026-1234 details" in prompt
        assert "GDPR timeline" in prompt

    async def test_deduplication(self, mock_llm):
        mock_llm.add_response("sonnet", "QUERIES:\n1. GDPR notification deadline\n")
        orch = SearchOrchestrator(mock_llm, search_fn=AsyncMock(return_value=[]), max_results=10)
        model_requests = ["GDPR notification deadline"]
        proactive = await orch.generate_proactive_queries(
            {"r1": "text"}, already_queued=model_requests,
        )
        combined = orch.deduplicate(model_requests + proactive)
        assert len(combined) <= len(model_requests) + len(proactive)

    async def test_topic_tracking_uses_sonar_for_repeat(self, mock_llm):
        search_fn = AsyncMock(return_value=[])
        sonar_fn = AsyncMock(return_value=[])
        orch = SearchOrchestrator(mock_llm, search_fn=search_fn, sonar_fn=sonar_fn, max_results=10)
        orch.mark_topic_searched("GDPR notification")
        await orch.execute_query("GDPR notification deadline", phase=SearchPhase.R2_R3)
        sonar_fn.assert_called_once()
        search_fn.assert_not_called()

    async def test_first_search_uses_playwright(self, mock_llm):
        search_fn = AsyncMock(return_value=[])
        sonar_fn = AsyncMock(return_value=[])
        orch = SearchOrchestrator(mock_llm, search_fn=search_fn, sonar_fn=sonar_fn, max_results=10)
        await orch.execute_query("CVE-2026-1234 details", phase=SearchPhase.R1_R2)
        search_fn.assert_called_once()
        sonar_fn.assert_not_called()

    async def test_max_results_respected(self, mock_llm):
        from brain.types import SearchResult
        many_results = [SearchResult(url=f"https://{i}.com", title=f"R{i}", snippet=f"s{i}") for i in range(20)]
        search_fn = AsyncMock(return_value=many_results)
        orch = SearchOrchestrator(mock_llm, search_fn=search_fn, max_results=10)
        results = await orch.execute_query("test query", phase=SearchPhase.R1_R2)
        assert len(results) <= 10
