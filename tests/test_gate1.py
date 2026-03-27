"""Tests for Gate 1: question quality assessment."""
import pytest

from thinker.gate1 import run_gate1, parse_gate1_response
from thinker.types import Outcome


class TestGate1Parsing:
    """Parse Sonnet's Gate 1 response."""

    def test_parse_pass(self):
        text = (
            "VERDICT: PASS\n"
            "QUESTIONS:\n"
            "REASONING: The brief provides a clear security incident with specific details."
        )
        result = parse_gate1_response(text)
        assert result.passed is True
        assert result.outcome == Outcome.DECIDE
        assert result.questions == []

    def test_parse_need_more(self):
        text = (
            "VERDICT: NEED_MORE\n"
            "QUESTIONS:\n"
            "- What version of the JWT library is in use?\n"
            "- Are there existing WAF rules in place?\n"
            "REASONING: The brief lacks specific technical details needed for assessment."
        )
        result = parse_gate1_response(text)
        assert result.passed is False
        assert result.outcome == Outcome.NEED_MORE
        assert len(result.questions) == 2
        assert "JWT library" in result.questions[0]

    def test_parse_malformed_defaults_to_pass(self):
        """If Sonnet's response is unparseable, pass the brief through."""
        result = parse_gate1_response("This is not a valid response format at all.")
        assert result.passed is True
        assert result.outcome == Outcome.DECIDE


class TestGate1Execution:
    """Gate 1 end-to-end with mock LLM."""

    async def test_clear_brief_passes(self, mock_llm):
        mock_llm.add_response("sonnet", (
            "VERDICT: PASS\n"
            "QUESTIONS:\n"
            "REASONING: Clear incident with specific CVE, timeline, and scope."
        ))
        result = await run_gate1(mock_llm, "JWT bypass incident with CVE-2026-1234...")
        assert result.passed is True
        assert mock_llm.call_count == 1

    async def test_vague_brief_pushes_back(self, mock_llm):
        mock_llm.add_response("sonnet", (
            "VERDICT: NEED_MORE\n"
            "QUESTIONS:\n"
            "- What system is affected?\n"
            "- When was the issue discovered?\n"
            "REASONING: The brief is too vague."
        ))
        result = await run_gate1(mock_llm, "Something is broken, what do?")
        assert result.passed is False
        assert result.outcome == Outcome.NEED_MORE
        assert len(result.questions) >= 1

    async def test_llm_failure_passes_through(self, mock_llm):
        """If Sonnet fails, don't block the brief — pass it through."""
        result = await run_gate1(mock_llm, "Any brief")
        # No mock response queued → LLM "fails"
        assert result.passed is True

    async def test_prompt_contains_brief(self, mock_llm):
        mock_llm.add_response("sonnet", "VERDICT: PASS\nQUESTIONS:\nREASONING: Fine.")
        await run_gate1(mock_llm, "My specific brief about JWT bypass")
        prompt = mock_llm.last_prompt_for("sonnet")
        assert "My specific brief about JWT bypass" in prompt
