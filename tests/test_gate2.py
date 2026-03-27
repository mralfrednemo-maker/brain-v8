"""Tests for Gate 2: deterministic trust assessment.

V8 spec: Gate 2 is fully deterministic. No LLM call.
Thresholds on mechanical tool data only.
"""
import pytest

from thinker.gate2 import run_gate2_deterministic, classify_outcome
from thinker.types import (
    Argument, ArgumentStatus, Blocker, BlockerKind, BlockerStatus,
    Confidence, Contradiction, Outcome, Position,
)


class TestClassifyOutcome:
    """Deterministic outcome classification."""

    def test_consensus(self):
        result = classify_outcome(
            agreement_ratio=1.0, ignored_arguments=0, mentioned_arguments=0,
            evidence_count=10, contradictions=0, open_blockers=0,
            search_enabled=True,
        )
        assert result == "CONSENSUS"

    def test_no_consensus_low_agreement(self):
        result = classify_outcome(
            agreement_ratio=0.3, ignored_arguments=0, mentioned_arguments=0,
            evidence_count=5, contradictions=0, open_blockers=0,
            search_enabled=True,
        )
        assert result == "NO_CONSENSUS"

    def test_no_consensus_many_ignored(self):
        result = classify_outcome(
            agreement_ratio=0.8, ignored_arguments=3, mentioned_arguments=0,
            evidence_count=5, contradictions=0, open_blockers=0,
            search_enabled=True,
        )
        assert result == "NO_CONSENSUS"

    def test_insufficient_evidence(self):
        result = classify_outcome(
            agreement_ratio=0.8, ignored_arguments=0, mentioned_arguments=0,
            evidence_count=0, contradictions=0, open_blockers=0,
            search_enabled=True,
        )
        assert result == "INSUFFICIENT_EVIDENCE"

    def test_closed_with_accepted_risks(self):
        result = classify_outcome(
            agreement_ratio=0.8, ignored_arguments=0, mentioned_arguments=0,
            evidence_count=5, contradictions=2, open_blockers=1,
            search_enabled=True,
        )
        assert result == "CLOSED_WITH_ACCEPTED_RISKS"

    def test_partial_consensus(self):
        result = classify_outcome(
            agreement_ratio=0.6, ignored_arguments=1, mentioned_arguments=1,
            evidence_count=5, contradictions=0, open_blockers=0,
            search_enabled=True,
        )
        assert result == "PARTIAL_CONSENSUS"

    def test_no_search_bypasses_evidence_check(self):
        """When search is disabled, evidence_count=0 doesn't trigger INSUFFICIENT_EVIDENCE."""
        result = classify_outcome(
            agreement_ratio=1.0, ignored_arguments=0, mentioned_arguments=0,
            evidence_count=0, contradictions=0, open_blockers=0,
            search_enabled=False,
        )
        assert result == "CONSENSUS"


class TestRunGate2Deterministic:
    """Gate 2 full deterministic execution."""

    def test_high_agreement_decides(self):
        result = run_gate2_deterministic(
            agreement_ratio=1.0,
            positions={
                "r1": Position("r1", 3, "O4", confidence=Confidence.HIGH),
                "reasoner": Position("reasoner", 3, "O4", confidence=Confidence.HIGH),
            },
            contradictions=[],
            unaddressed_arguments=[],
            open_blockers=[],
            evidence_count=10,
            search_enabled=True,
        )
        assert result.outcome == Outcome.DECIDE
        assert result.convergence_ok is True
        assert result.dissent_addressed is True

    def test_low_agreement_escalates(self):
        result = run_gate2_deterministic(
            agreement_ratio=0.3,
            positions={},
            contradictions=[],
            unaddressed_arguments=[],
            open_blockers=[],
            evidence_count=5,
            search_enabled=True,
        )
        assert result.outcome == Outcome.ESCALATE
        assert result.convergence_ok is False

    def test_ignored_arguments_escalate(self):
        result = run_gate2_deterministic(
            agreement_ratio=1.0,
            positions={
                "r1": Position("r1", 3, "O4", confidence=Confidence.HIGH),
            },
            contradictions=[],
            unaddressed_arguments=[
                Argument("ARG-5", 2, "glm5", "Insider threat ignored", status=ArgumentStatus.IGNORED),
            ],
            open_blockers=[],
            evidence_count=10,
            search_enabled=True,
        )
        assert result.outcome == Outcome.ESCALATE
        assert result.dissent_addressed is False

    def test_mentioned_but_not_ignored_decides(self):
        """MENTIONED arguments don't block DECIDE — only IGNORED ones do."""
        result = run_gate2_deterministic(
            agreement_ratio=1.0,
            positions={
                "r1": Position("r1", 3, "O4", confidence=Confidence.HIGH),
            },
            contradictions=[],
            unaddressed_arguments=[
                Argument("ARG-5", 2, "glm5", "Some point", status=ArgumentStatus.MENTIONED),
            ],
            open_blockers=[],
            evidence_count=10,
            search_enabled=True,
        )
        assert result.outcome == Outcome.DECIDE

    def test_reasoning_includes_classification(self):
        result = run_gate2_deterministic(
            agreement_ratio=1.0,
            positions={},
            contradictions=[],
            unaddressed_arguments=[],
            open_blockers=[],
            evidence_count=10,
            search_enabled=True,
        )
        assert "class=CONSENSUS" in result.reasoning

    def test_no_search_still_decides(self):
        """Without search, evidence_count=0 is acceptable."""
        result = run_gate2_deterministic(
            agreement_ratio=1.0,
            positions={},
            contradictions=[],
            unaddressed_arguments=[],
            open_blockers=[],
            evidence_count=0,
            search_enabled=False,
        )
        assert result.outcome == Outcome.DECIDE
        assert result.evidence_credible is True
