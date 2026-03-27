"""Tests for round execution."""
import pytest

from thinker.rounds import execute_round, build_round_prompt
from thinker.config import ROUND_TOPOLOGY
from thinker.types import RoundResult


class TestRound1:
    """Round 1: independent opinions, just the brief."""

    async def test_r1_calls_4_models(self, mock_llm):
        for model in ROUND_TOPOLOGY[1]:
            mock_llm.add_response(model, f"Analysis from {model}")
        result = await execute_round(mock_llm, round_num=1, brief="Test brief", is_last_round=False)
        assert len(result.responded) == 4
        assert result.failed == []

    async def test_r1_prompt_contains_only_brief(self, mock_llm):
        for model in ROUND_TOPOLOGY[1]:
            mock_llm.add_response(model, "Analysis")
        await execute_round(mock_llm, round_num=1, brief="My test brief about JWT", is_last_round=False)
        prompt = mock_llm.last_prompt_for("r1")
        assert "My test brief about JWT" in prompt
        # R1 should NOT contain evidence or prior round views
        assert "evidence" not in prompt.lower() or "Web-Verified Evidence" not in prompt

    async def test_r1_handles_model_failure(self, mock_llm):
        mock_llm.add_response("r1", "Analysis from r1")
        mock_llm.add_response("reasoner", "Analysis from reasoner")
        mock_llm.add_response("glm5", "Analysis from glm5")
        # kimi has no response → will fail
        result = await execute_round(mock_llm, round_num=1, brief="Test", is_last_round=False)
        assert len(result.responded) == 3
        assert "kimi" not in result.responded


class TestRound1Prompt:
    """Round 1 prompt structure."""

    def test_r1_prompt_has_brief(self):
        prompt = build_round_prompt(
            round_num=1, brief="JWT bypass incident", prior_views={},
            evidence_text="", unaddressed_arguments="",
            is_last_round=False,
        )
        assert "JWT bypass incident" in prompt

    def test_r1_prompt_no_prior_views(self):
        prompt = build_round_prompt(
            round_num=1, brief="Brief", prior_views={},
            evidence_text="", unaddressed_arguments="",
            is_last_round=False,
        )
        assert "prior round" not in prompt.lower()

    def test_r1_prompt_has_search_request_section(self):
        prompt = build_round_prompt(
            round_num=1, brief="Brief", prior_views={},
            evidence_text="", unaddressed_arguments="",
            is_last_round=False,
        )
        assert "SEARCH_REQUESTS" in prompt or "Search Requests" in prompt

    def test_last_round_no_search_request_section(self):
        prompt = build_round_prompt(
            round_num=1, brief="Brief", prior_views={},
            evidence_text="", unaddressed_arguments="",
            is_last_round=True,
        )
        assert "Search Requests" not in prompt


class TestRound2Prompt:
    """Round 2 prompt includes R1 views + evidence."""

    def test_r2_prompt_includes_r1_views(self):
        prompt = build_round_prompt(
            round_num=2, brief="Brief",
            prior_views={
                "r1": "R1 thinks X",
                "reasoner": "Reasoner thinks Y",
                "glm5": "GLM5 thinks Z",
                "kimi": "Kimi thinks W",
            },
            evidence_text="{E001} Some fact\nSource: https://example.com",
            unaddressed_arguments="",
            is_last_round=False,
        )
        assert "R1 thinks X" in prompt
        assert "Reasoner thinks Y" in prompt
        assert "{E001}" in prompt

    def test_r2_prompt_includes_evidence_header(self):
        prompt = build_round_prompt(
            round_num=2, brief="Brief",
            prior_views={"r1": "view"},
            evidence_text="{E001} Some fact\nSource: https://example.com",
            unaddressed_arguments="",
            is_last_round=False,
        )
        assert "Web-Verified Evidence" in prompt
        assert "outranks model opinions" in prompt

    def test_r2_prompt_includes_unaddressed_arguments(self):
        prompt = build_round_prompt(
            round_num=2, brief="Brief",
            prior_views={"r1": "view"},
            evidence_text="",
            unaddressed_arguments="ARG-1: [r1] The breach timeline suggests insider access\nARG-2: [glm5] Regulatory notification deadline is 72 hours",
            is_last_round=False,
        )
        assert "ARG-1" in prompt
        assert "MUST engage" in prompt


class TestRound34:
    """Rounds 3-4: narrower topology, still include evidence + arguments."""

    async def test_r3_calls_2_models(self, mock_llm):
        for model in ROUND_TOPOLOGY[3]:
            mock_llm.add_response(model, f"Analysis from {model}")
        result = await execute_round(
            mock_llm, round_num=3, brief="Brief",
            prior_views={"r1": "v1", "reasoner": "v2", "glm5": "v3"},
            evidence_text="evidence", unaddressed_arguments="",
            is_last_round=True,
        )
        assert len(result.responded) == 2
        assert set(result.responded) == {"r1", "reasoner"}
