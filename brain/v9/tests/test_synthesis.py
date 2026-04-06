"""Tests for Hermes synthesis."""
import pytest

from brain.synthesis import run_synthesis, build_synthesis_prompt
from brain.types import BrainError


class TestSynthesisPrompt:
    """Synthesis prompt structure per V8 spec."""

    def test_prompt_includes_only_final_round_views(self):
        """V8 spec: Synthesis sees ONLY R4 views. 'DO NOT INVENT NEW ARGUMENTS.'"""
        prompt = build_synthesis_prompt(
            brief="JWT bypass incident...",
            final_views={"r1": "R4 view from R1", "reasoner": "R4 view from reasoner"},
            blocker_summary={"open_at_end": 0, "total_blockers": 3},
        )
        assert "R4 view from R1" in prompt
        assert "R4 view from reasoner" in prompt
        assert "DO NOT INVENT NEW ARGUMENTS" in prompt

    def test_prompt_includes_blocker_summary(self):
        prompt = build_synthesis_prompt(
            brief="Brief",
            final_views={"r1": "view"},
            blocker_summary={"open_at_end": 1, "total_blockers": 5},
        )
        assert "5" in prompt  # total blockers
        assert "blocker" in prompt.lower()


class TestSynthesisExecution:

    async def test_synthesis_returns_tuple(self, mock_llm):
        """run_synthesis returns (markdown, json_data) tuple."""
        mock_llm.add_response("sonnet", (
            "# Deliberation Report\n\n## TL;DR\nModels reached consensus on full shutdown.\n"
            "\n---JSON---\n\n"
            '{"title": "Security Incident", "tldr": "Consensus on shutdown", '
            '"verdict": "Full shutdown", "confidence": "high", '
            '"agreed_points": ["shutdown"], "contested_points": [], '
            '"key_findings": ["RCE confirmed"], "risk_factors": [], '
            '"evidence_cited": ["E001"], "unresolved_questions": []}'
        ))
        markdown, json_data, _dispositions = await run_synthesis(
            mock_llm, brief="Brief", final_views={"r1": "v", "reasoner": "v"},
            blocker_summary={}, outcome_class="CONSENSUS",
        )
        assert "# Deliberation Report" in markdown
        assert "CONSENSUS" in markdown
        assert isinstance(json_data, dict)
        assert json_data["outcome_class"] == "CONSENSUS"

    async def test_synthesis_without_json_section(self, mock_llm):
        """If LLM doesn't produce ---JSON--- separator, still returns tuple."""
        mock_llm.add_response("sonnet", (
            "# Deliberation Report\n\n## TL;DR\nModels reached consensus.\n"
        ))
        markdown, json_data, _dispositions = await run_synthesis(
            mock_llm, brief="Brief", final_views={"r1": "v"},
            blocker_summary={}, outcome_class="CONSENSUS",
        )
        assert "# Deliberation Report" in markdown
        assert isinstance(json_data, dict)

    async def test_synthesis_failure_raises_brain_error(self, mock_llm):
        """If Sonnet fails during synthesis, raise BrainError — zero tolerance."""
        with pytest.raises(BrainError) as exc_info:
            await run_synthesis(
                mock_llm, brief="Brief", final_views={"r1": "v"},
                blocker_summary={},
            )
        assert exc_info.value.stage == "synthesis"

    async def test_outcome_class_appended(self, mock_llm):
        """outcome_class is appended to markdown and json_data."""
        mock_llm.add_response("sonnet", "# Report\n\n---JSON---\n\n{}")
        markdown, json_data, _dispositions = await run_synthesis(
            mock_llm, brief="Brief", final_views={"r1": "v"},
            blocker_summary={}, outcome_class="PARTIAL_CONSENSUS",
        )
        assert "PARTIAL_CONSENSUS" in markdown
        assert json_data["outcome_class"] == "PARTIAL_CONSENSUS"
