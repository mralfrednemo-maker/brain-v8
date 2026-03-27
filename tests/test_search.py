"""Tests for the search system."""
import pytest
from unittest.mock import AsyncMock, patch

from thinker.search import SearchOrchestrator, SearchPhase
from thinker.types import EvidenceItem, Confidence


class TestSearchOrchestrator:
    """Search orchestration: reactive + proactive queries."""

    async def test_reactive_queries_extracted(self, mock_llm):
        mock_llm.add_response("sonnet", (
            "QUERIES:\n"
            "1. CVE-2026-1234 JWT bypass severity CVSS score\n"
            "2. GDPR Article 33 notification timeline requirements\n"
            "3. SOC 2 breach reporting obligations\n"
        ))
        orch = SearchOrchestrator(mock_llm, search_fn=AsyncMock(return_value=[]))
        queries = await orch.generate_reactive_queries({
            "r1": "JWT bypass is critical, CVSS unknown",
            "glm5": "Need to check GDPR timeline",
        })
        assert len(queries) >= 2

    async def test_proactive_queries_from_claims(self, mock_llm):
        mock_llm.add_response("sonnet", (
            "CLAIMS:\n"
            "1. '847 requests' — verify actual log count\n"
            "2. '72 hours' — verify GDPR notification deadline\n"
            "QUERIES:\n"
            "1. GDPR Article 33 breach notification deadline hours\n"
        ))
        orch = SearchOrchestrator(mock_llm, search_fn=AsyncMock(return_value=[]))
        queries = await orch.generate_proactive_queries({
            "r1": "The 847 requests over 33 minutes suggest automated exploitation",
            "kimi": "GDPR requires notification within 72 hours",
        })
        assert len(queries) >= 1

    async def test_deduplication(self, mock_llm):
        mock_llm.add_response("sonnet", "QUERIES:\n1. GDPR notification deadline\n")
        mock_llm.add_response("sonnet", "CLAIMS:\n1. 72h\nQUERIES:\n1. GDPR notification deadline\n")
        orch = SearchOrchestrator(mock_llm, search_fn=AsyncMock(return_value=[]))
        reactive = await orch.generate_reactive_queries({"r1": "text"})
        proactive = await orch.generate_proactive_queries({"r1": "text"})
        combined = orch.deduplicate(reactive + proactive)
        assert len(combined) <= len(reactive) + len(proactive)

    async def test_topic_tracking_uses_sonar_for_repeat(self, mock_llm):
        search_fn = AsyncMock(return_value=[])
        sonar_fn = AsyncMock(return_value=[])
        orch = SearchOrchestrator(mock_llm, search_fn=search_fn, sonar_fn=sonar_fn)
        orch.mark_topic_searched("GDPR notification")
        await orch.execute_query("GDPR notification deadline", phase=SearchPhase.R2_R3)
        sonar_fn.assert_called_once()
        search_fn.assert_not_called()

    async def test_first_search_uses_playwright(self, mock_llm):
        search_fn = AsyncMock(return_value=[])
        sonar_fn = AsyncMock(return_value=[])
        orch = SearchOrchestrator(mock_llm, search_fn=search_fn, sonar_fn=sonar_fn)
        await orch.execute_query("CVE-2026-1234 details", phase=SearchPhase.R1_R2)
        search_fn.assert_called_once()
        sonar_fn.assert_not_called()


class TestFactExtraction:
    """LLM extracts facts from full page content."""

    async def test_extract_facts_from_page(self, mock_llm):
        mock_llm.add_response("sonnet", (
            "FACTS:\n"
            "- {E001} [HIGH] GDPR Article 33 requires notification within 72 hours of breach discovery\n"
            "- {E002} [MEDIUM] Notification must be made to supervisory authority, not just data subjects\n"
        ))
        orch = SearchOrchestrator(mock_llm, search_fn=AsyncMock(return_value=[]))
        facts = await orch.extract_facts(
            page_content="Full article about GDPR Article 33...",
            url="https://gdpr-info.eu/art-33",
            query="GDPR notification deadline",
        )
        assert len(facts) >= 1
        assert facts[0].evidence_id == "E001"
