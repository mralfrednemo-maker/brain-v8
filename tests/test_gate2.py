"""Tests for Gate 2: trust assessment.

V8 spec: Gate 2 is LLM judgment backed by mechanical tool data.
The tools provide DATA (contradictions, gaps, positions). The LLM provides JUDGMENT.
"""
import pytest

from thinker.gate2 import run_gate2, build_gate2_prompt
from thinker.types import (
    Argument, ArgumentStatus, Blocker, BlockerKind, BlockerStatus,
    Confidence, Contradiction, Outcome, Position,
)


class TestGate2Prompting:
    """Gate 2 prompt construction includes tool data."""

    def test_prompt_includes_convergence_data(self):
        prompt = build_gate2_prompt(
            agreement_ratio=1.0,
            positions={"r1": Position("r1", 3, "O4", confidence=Confidence.HIGH),
                       "reasoner": Position("reasoner", 3, "O4", confidence=Confidence.HIGH)},
            contradictions=[],
            unaddressed_arguments=[],
            open_blockers=[],
            evidence_count=10,
            report_text="Report text...",
        )
        assert "agreement_ratio: 1.0" in prompt
        assert "O4" in prompt

    def test_prompt_includes_contradictions(self):
        prompt = build_gate2_prompt(
            agreement_ratio=0.5,
            positions={},
            contradictions=[
                Contradiction("CTR001", ["E001", "E002"], "breach scope", "HIGH"),
            ],
            unaddressed_arguments=[],
            open_blockers=[],
            evidence_count=5,
            report_text="Report...",
        )
        assert "CTR001" in prompt
        assert "breach scope" in prompt

    def test_prompt_includes_unaddressed_arguments(self):
        prompt = build_gate2_prompt(
            agreement_ratio=0.8,
            positions={},
            contradictions=[],
            unaddressed_arguments=[
                Argument("ARG-5", 2, "glm5", "Insider threat ignored", status=ArgumentStatus.IGNORED),
            ],
            open_blockers=[],
            evidence_count=8,
            report_text="Report...",
        )
        assert "ARG-5" in prompt
        assert "Insider threat" in prompt


class TestGate2Execution:
    """Gate 2 full execution with mock LLM."""

    async def test_high_confidence_decides(self, mock_llm):
        mock_llm.add_response("sonnet", (
            "CONVERGENCE: YES — Both models agree on O4 for the same reasons (active RCE requires immediate shutdown)\n"
            "EVIDENCE: YES — 10 items from authoritative sources (NVD, GDPR official text), cross-corroborated\n"
            "DISSENT: YES — All significant arguments were addressed by final round\n"
            "DATA: YES — Key claims verified: CVE severity, breach notification timeline, response options\n"
            "REPORT: YES — Report genuinely engages with all blockers and contradictions\n"
            "VERDICT: DECIDE\n"
            "REASONING: Strong convergence with evidence-driven agreement. All dissent addressed."
        ))
        result = await run_gate2(
            mock_llm, agreement_ratio=1.0,
            positions={"r1": Position("r1", 4, "O4"), "reasoner": Position("reasoner", 4, "O4")},
            contradictions=[], unaddressed_arguments=[], open_blockers=[],
            evidence_count=10, report_text="Solid report...",
        )
        assert result.outcome == Outcome.DECIDE
        assert result.convergence_ok is True

    async def test_low_confidence_escalates(self, mock_llm):
        mock_llm.add_response("sonnet", (
            "CONVERGENCE: NO — Models agree on label but disagree on reasoning\n"
            "EVIDENCE: NO — Only 2 items found, both from secondary sources\n"
            "DISSENT: NO — ARG-5 about insider threat was never addressed\n"
            "DATA: NO — Key claims about breach scope remain unverified\n"
            "REPORT: YES — Report mentions blockers\n"
            "VERDICT: ESCALATE\n"
            "REASONING: Insufficient evidence and unresolved dissent. Human review needed."
        ))
        result = await run_gate2(
            mock_llm, agreement_ratio=0.5,
            positions={}, contradictions=[], unaddressed_arguments=[],
            open_blockers=[], evidence_count=2, report_text="Weak report...",
        )
        assert result.outcome == Outcome.ESCALATE

    async def test_llm_failure_escalates(self, mock_llm):
        """If Gate 2 LLM fails, escalate (conservative)."""
        result = await run_gate2(
            mock_llm, agreement_ratio=1.0,
            positions={}, contradictions=[], unaddressed_arguments=[],
            open_blockers=[], evidence_count=10, report_text="...",
        )
        assert result.outcome == Outcome.ESCALATE
