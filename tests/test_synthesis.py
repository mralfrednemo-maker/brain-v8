"""Tests for Hermes synthesis."""
import pytest

from thinker.synthesis import run_synthesis, build_synthesis_prompt


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

    async def test_synthesis_returns_report(self, mock_llm):
        mock_llm.add_response("sonnet", (
            "---\n"
            "final_status: COMPLETE\n"
            "v3_outcome_class: CONSENSUS\n"
            "confidence: high\n"
            "---\n\n"
            "# Deliberation Report\n\n## TL;DR\nModels reached consensus on full shutdown.\n"
        ))
        report = await run_synthesis(
            mock_llm, brief="Brief", final_views={"r1": "v", "reasoner": "v"},
            blocker_summary={},
        )
        assert "CONSENSUS" in report
        assert "# Deliberation Report" in report

    async def test_synthesis_failure_returns_degraded(self, mock_llm):
        """If Hermes fails, return a degraded report."""
        report = await run_synthesis(
            mock_llm, brief="Brief", final_views={"r1": "v"},
            blocker_summary={},
        )
        assert "DEGRADED" in report or "failed" in report.lower()
