"""Tests for Gate 2: deterministic trust assessment with D1-D14 / A1-A7 rule sets.

V9 spec: Gate 2 is fully deterministic. No LLM call.
D1-D14 for DECIDE modality, A1-A7 for ANALYSIS modality.
First matching rule wins. Every rule evaluated is recorded in rule_trace.
"""
import pytest

from thinker.gate2 import run_gate2_deterministic, classify_outcome
from thinker.types import (
    Argument, ArgumentStatus, Blocker, BlockerKind, BlockerStatus,
    Confidence, Contradiction, DecisiveClaim, DimensionItem,
    DimensionSeedResult, DivergenceResult, EvidenceSupportStatus,
    FrameInfo, FrameSurvivalStatus, FrameType, Modality, Outcome,
    Position, PreflightResult, StabilityResult, StakesClass,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _positions(n: int = 2) -> dict[str, Position]:
    """Create n dummy positions with HIGH confidence."""
    models = ["r1", "reasoner", "glm5", "kimi"][:n]
    return {m: Position(m, 3, "O4", confidence=Confidence.HIGH) for m in models}


def _preflight_decide(**kwargs) -> PreflightResult:
    """PreflightResult with DECIDE modality (default)."""
    defaults = {"modality": Modality.DECIDE}
    defaults.update(kwargs)
    return PreflightResult(**defaults)


def _preflight_analysis(**kwargs) -> PreflightResult:
    """PreflightResult with ANALYSIS modality."""
    defaults = {"modality": Modality.ANALYSIS}
    defaults.update(kwargs)
    return PreflightResult(**defaults)


def _stability(**kwargs) -> StabilityResult:
    return StabilityResult(**kwargs)


def _divergence(material_unrebutted: int = 0) -> DivergenceResult:
    """Create DivergenceResult with the given number of material unrebutted frames."""
    frames = []
    for i in range(material_unrebutted):
        frames.append(FrameInfo(
            frame_id=f"F-{i+1}",
            text=f"Frame {i+1}",
            material_to_outcome=True,
            survival_status=FrameSurvivalStatus.ACTIVE,
        ))
    return DivergenceResult(alt_frames=frames)


def _dimensions(items: list[DimensionItem] = None, coverage: float = 1.0) -> DimensionSeedResult:
    return DimensionSeedResult(
        items=items or [],
        dimension_count=len(items) if items else 0,
        dimension_coverage_score=coverage,
    )


def _decisive_claims_supported(n: int = 2) -> list[DecisiveClaim]:
    return [
        DecisiveClaim(
            claim_id=f"DC-{i+1}", text=f"Claim {i+1}",
            material_to_conclusion=True,
            evidence_support_status=EvidenceSupportStatus.SUPPORTED,
        )
        for i in range(n)
    ]


def _decisive_claims_unsupported(n: int = 1) -> list[DecisiveClaim]:
    return [
        DecisiveClaim(
            claim_id=f"DC-{i+1}", text=f"Claim {i+1}",
            material_to_conclusion=True,
            evidence_support_status=EvidenceSupportStatus.UNSUPPORTED,
        )
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# classify_outcome (V8 compat)
# ---------------------------------------------------------------------------

class TestClassifyOutcome:
    """Deterministic outcome classification (legacy V8)."""

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

    def test_many_ignored_with_high_agreement_is_partial(self):
        result = classify_outcome(
            agreement_ratio=0.8, ignored_arguments=3, mentioned_arguments=0,
            evidence_count=5, contradictions=0, open_blockers=0,
            search_enabled=True,
        )
        assert result == "PARTIAL_CONSENSUS"

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
        result = classify_outcome(
            agreement_ratio=1.0, ignored_arguments=0, mentioned_arguments=0,
            evidence_count=0, contradictions=0, open_blockers=0,
            search_enabled=False,
        )
        assert result == "CONSENSUS"


# ---------------------------------------------------------------------------
# Backward compatibility: basic params only (no V9 objects)
# ---------------------------------------------------------------------------

class TestBackwardCompat:
    """Old code calling with just the basic params should still work."""

    def test_high_agreement_decides(self):
        result = run_gate2_deterministic(
            agreement_ratio=1.0,
            positions=_positions(2),
            contradictions=[],
            unaddressed_arguments=[],
            open_blockers=[],
            evidence_count=10,
            search_enabled=True,
        )
        assert result.outcome == Outcome.DECIDE
        assert result.convergence_ok is True
        assert result.dissent_addressed is True

    def test_low_agreement_no_consensus(self):
        """Without V9 objects, low agreement falls through to D10 -> NO_CONSENSUS."""
        result = run_gate2_deterministic(
            agreement_ratio=0.3,
            positions={},
            contradictions=[],
            unaddressed_arguments=[],
            open_blockers=[],
            evidence_count=5,
            search_enabled=True,
        )
        # V9 D10: agreement < 0.50 without HIGH stakes -> NO_CONSENSUS
        assert result.outcome == Outcome.NO_CONSENSUS
        assert result.convergence_ok is False

    def test_few_ignored_with_high_agreement_still_decides(self):
        result = run_gate2_deterministic(
            agreement_ratio=1.0,
            positions=_positions(1),
            contradictions=[],
            unaddressed_arguments=[
                Argument("ARG-5", 2, "glm5", "Minor point ignored", status=ArgumentStatus.IGNORED),
            ],
            open_blockers=[],
            evidence_count=10,
            search_enabled=True,
        )
        assert result.outcome == Outcome.DECIDE

    def test_mentioned_but_not_ignored_decides(self):
        result = run_gate2_deterministic(
            agreement_ratio=1.0,
            positions=_positions(1),
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


# ---------------------------------------------------------------------------
# DECIDE rules D1-D14
# ---------------------------------------------------------------------------

class TestDecideRules:
    """D1-D14 rule evaluation for DECIDE modality."""

    def test_d1_high_agreement_no_blockers_stable(self):
        """D1: agreement>=0.75, no blockers, stable -> DECIDE."""
        result = run_gate2_deterministic(
            agreement_ratio=0.80,
            positions=_positions(2),
            contradictions=[],
            unaddressed_arguments=[],
            open_blockers=[],
            evidence_count=5,
            search_enabled=True,
            preflight=_preflight_decide(),
            stability=_stability(conclusion_stable=True),
        )
        assert result.outcome == Outcome.DECIDE
        matched = [r for r in result.rule_trace if r["matched"]]
        assert matched[0]["rule"] == "D1"

    def test_d2_high_agreement_low_severity_blockers(self):
        """D2: agreement>=0.75, blockers present but all LOW -> DECIDE."""
        blocker = Blocker("B-1", BlockerKind.EVIDENCE_GAP, "r1", 2, status=BlockerStatus.OPEN)
        result = run_gate2_deterministic(
            agreement_ratio=0.80,
            positions=_positions(2),
            contradictions=[],
            unaddressed_arguments=[],
            open_blockers=[blocker],
            evidence_count=5,
            search_enabled=True,
            preflight=_preflight_decide(),
            stability=_stability(conclusion_stable=True),
        )
        assert result.outcome == Outcome.DECIDE
        matched = [r for r in result.rule_trace if r["matched"]]
        assert matched[0]["rule"] == "D2"

    def test_d3_high_agreement_groupthink(self):
        """D3: agreement>=0.75, groupthink warning -> ESCALATE."""
        result = run_gate2_deterministic(
            agreement_ratio=0.90,
            positions=_positions(2),
            contradictions=[],
            unaddressed_arguments=[],
            open_blockers=[],
            evidence_count=5,
            search_enabled=True,
            preflight=_preflight_decide(),
            stability=_stability(conclusion_stable=False, groupthink_warning=True),
        )
        assert result.outcome == Outcome.ESCALATE
        matched = [r for r in result.rule_trace if r["matched"]]
        assert matched[0]["rule"] == "D3"

    def test_d4_moderate_agreement_evidence_claims(self):
        """D4: agreement>=0.50, evidence>=3, claims supported -> DECIDE."""
        result = run_gate2_deterministic(
            agreement_ratio=0.60,
            positions=_positions(2),
            contradictions=[],
            unaddressed_arguments=[],
            open_blockers=[],
            evidence_count=5,
            search_enabled=True,
            preflight=_preflight_decide(),
            stability=_stability(),
            decisive_claims=_decisive_claims_supported(2),
            divergence=_divergence(0),
        )
        assert result.outcome == Outcome.DECIDE
        matched = [r for r in result.rule_trace if r["matched"]]
        assert matched[0]["rule"] == "D4"

    def test_d5_moderate_agreement_unrebutted_frames(self):
        """D5: agreement>=0.50, material unrebutted frames -> ESCALATE."""
        result = run_gate2_deterministic(
            agreement_ratio=0.60,
            positions=_positions(2),
            contradictions=[],
            unaddressed_arguments=[],
            open_blockers=[],
            evidence_count=5,
            search_enabled=True,
            preflight=_preflight_decide(),
            stability=_stability(),
            divergence=_divergence(material_unrebutted=2),
        )
        assert result.outcome == Outcome.ESCALATE
        matched = [r for r in result.rule_trace if r["matched"]]
        assert matched[0]["rule"] == "D5"

    def test_d6_moderate_agreement_unresolved_contradictions(self):
        """D6: agreement>=0.50, unresolved contradictions -> ESCALATE."""
        ctr = Contradiction("CTR-1", ["E-1", "E-2"], "topic", "HIGH", status="OPEN")
        result = run_gate2_deterministic(
            agreement_ratio=0.60,
            positions=_positions(2),
            contradictions=[ctr],
            unaddressed_arguments=[],
            open_blockers=[],
            evidence_count=5,
            search_enabled=True,
            preflight=_preflight_decide(),
            stability=_stability(),
            divergence=_divergence(0),
        )
        assert result.outcome == Outcome.ESCALATE
        matched = [r for r in result.rule_trace if r["matched"]]
        assert matched[0]["rule"] == "D6"

    def test_d7_moderate_agreement_no_evidence(self):
        """D7: agreement>=0.50, no evidence, search enabled -> ESCALATE."""
        result = run_gate2_deterministic(
            agreement_ratio=0.60,
            positions=_positions(2),
            contradictions=[],
            unaddressed_arguments=[],
            open_blockers=[],
            evidence_count=0,
            search_enabled=True,
            preflight=_preflight_decide(),
            stability=_stability(),
            divergence=_divergence(0),
        )
        assert result.outcome == Outcome.ESCALATE
        matched = [r for r in result.rule_trace if r["matched"]]
        assert matched[0]["rule"] == "D7"

    def test_d8_low_agreement_high_stakes(self):
        """D8: agreement<0.50, HIGH stakes -> ESCALATE."""
        result = run_gate2_deterministic(
            agreement_ratio=0.30,
            positions=_positions(2),
            contradictions=[],
            unaddressed_arguments=[],
            open_blockers=[],
            evidence_count=5,
            search_enabled=True,
            preflight=_preflight_decide(stakes_class=StakesClass.HIGH),
            stability=_stability(),
        )
        assert result.outcome == Outcome.ESCALATE
        matched = [r for r in result.rule_trace if r["matched"]]
        assert matched[0]["rule"] == "D8"

    def test_d9_low_agreement_coverage_gaps(self):
        """D9: agreement<0.50, coverage gaps -> NO_CONSENSUS."""
        dims = _dimensions(
            items=[DimensionItem("DIM-1", "Economics", mandatory=True, coverage_status="ZERO")],
            coverage=0.0,
        )
        result = run_gate2_deterministic(
            agreement_ratio=0.30,
            positions=_positions(2),
            contradictions=[],
            unaddressed_arguments=[],
            open_blockers=[],
            evidence_count=5,
            search_enabled=True,
            preflight=_preflight_decide(stakes_class=StakesClass.STANDARD),
            stability=_stability(),
            dimensions=dims,
        )
        assert result.outcome == Outcome.NO_CONSENSUS
        matched = [r for r in result.rule_trace if r["matched"]]
        assert matched[0]["rule"] == "D9"

    def test_d10_low_agreement_fallback(self):
        """D10: agreement<0.50 (no HIGH stakes, no gaps) -> NO_CONSENSUS."""
        result = run_gate2_deterministic(
            agreement_ratio=0.30,
            positions=_positions(2),
            contradictions=[],
            unaddressed_arguments=[],
            open_blockers=[],
            evidence_count=5,
            search_enabled=True,
            preflight=_preflight_decide(stakes_class=StakesClass.STANDARD),
            stability=_stability(),
        )
        assert result.outcome == Outcome.NO_CONSENSUS
        matched = [r for r in result.rule_trace if r["matched"]]
        assert matched[0]["rule"] == "D10"

    def test_d11_fatal_premise(self):
        """D11: fatal_premise -> NEED_MORE (only reachable if agreement >= 0.50)."""
        result = run_gate2_deterministic(
            agreement_ratio=0.70,
            positions=_positions(2),
            contradictions=[],
            unaddressed_arguments=[],
            open_blockers=[],
            evidence_count=5,
            search_enabled=True,
            preflight=_preflight_decide(fatal_premise=True),
            stability=_stability(conclusion_stable=False),
            divergence=_divergence(0),
        )
        assert result.outcome == Outcome.NEED_MORE
        matched = [r for r in result.rule_trace if r["matched"]]
        assert matched[0]["rule"] == "D11"

    def test_d12_no_models(self):
        """D12: no models responded -> ERROR."""
        result = run_gate2_deterministic(
            agreement_ratio=0.70,
            positions={},
            contradictions=[],
            unaddressed_arguments=[],
            open_blockers=[],
            evidence_count=5,
            search_enabled=True,
            preflight=_preflight_decide(),
            stability=_stability(conclusion_stable=False),
            divergence=_divergence(0),
            total_arguments=10,
        )
        assert result.outcome == Outcome.ERROR
        matched = [r for r in result.rule_trace if r["matched"]]
        assert matched[0]["rule"] == "D12"

    def test_d13_zero_arguments(self):
        """D13: zero arguments tracked -> ERROR."""
        result = run_gate2_deterministic(
            agreement_ratio=0.70,
            positions=_positions(1),
            contradictions=[],
            unaddressed_arguments=[],
            open_blockers=[],
            evidence_count=5,
            search_enabled=True,
            preflight=_preflight_decide(),
            stability=_stability(conclusion_stable=False),
            divergence=_divergence(0),
            total_arguments=0,
        )
        assert result.outcome == Outcome.ERROR
        matched = [r for r in result.rule_trace if r["matched"]]
        assert matched[0]["rule"] == "D13"

    def test_d14_fallback(self):
        """D14: no prior rule matched -> ESCALATE."""
        result = run_gate2_deterministic(
            agreement_ratio=0.70,
            positions=_positions(2),
            contradictions=[],
            unaddressed_arguments=[],
            open_blockers=[],
            evidence_count=5,
            search_enabled=True,
            preflight=_preflight_decide(),
            stability=_stability(conclusion_stable=False),
            divergence=_divergence(0),
            total_arguments=10,
        )
        assert result.outcome == Outcome.ESCALATE
        matched = [r for r in result.rule_trace if r["matched"]]
        assert matched[0]["rule"] == "D14"


# ---------------------------------------------------------------------------
# ANALYSIS rules A1-A7
# ---------------------------------------------------------------------------

class TestAnalysisRules:
    """A1-A7 rule evaluation for ANALYSIS modality."""

    def test_a1_all_dimensions_explored(self):
        """A1: all dimensions explored -> ANALYSIS."""
        dims = _dimensions(
            items=[
                DimensionItem("DIM-1", "Economics", mandatory=True, coverage_status="SATISFIED"),
                DimensionItem("DIM-2", "Ethics", mandatory=True, coverage_status="PARTIAL"),
            ],
            coverage=0.8,
        )
        result = run_gate2_deterministic(
            agreement_ratio=0.60,
            positions=_positions(2),
            contradictions=[],
            unaddressed_arguments=[],
            open_blockers=[],
            evidence_count=5,
            search_enabled=True,
            preflight=_preflight_analysis(),
            dimensions=dims,
        )
        assert result.outcome == Outcome.ANALYSIS
        matched = [r for r in result.rule_trace if r["matched"]]
        assert matched[0]["rule"] == "A1"

    def test_a2_low_dimension_coverage(self):
        """A2: dimension_coverage < 0.5 -> NO_CONSENSUS."""
        dims = _dimensions(
            items=[
                DimensionItem("DIM-1", "Economics", mandatory=True, coverage_status="ZERO"),
                DimensionItem("DIM-2", "Ethics", mandatory=True, coverage_status="ZERO"),
            ],
            coverage=0.0,
        )
        result = run_gate2_deterministic(
            agreement_ratio=0.60,
            positions=_positions(2),
            contradictions=[],
            unaddressed_arguments=[],
            open_blockers=[],
            evidence_count=5,
            search_enabled=True,
            preflight=_preflight_analysis(),
            dimensions=dims,
        )
        assert result.outcome == Outcome.NO_CONSENSUS
        matched = [r for r in result.rule_trace if r["matched"]]
        assert matched[0]["rule"] == "A2"

    def test_a3_hypothesis_populated(self):
        """A3: hypothesis ledger (decisive_claims) populated -> ANALYSIS."""
        result = run_gate2_deterministic(
            agreement_ratio=0.60,
            positions=_positions(2),
            contradictions=[],
            unaddressed_arguments=[],
            open_blockers=[],
            evidence_count=5,
            search_enabled=True,
            preflight=_preflight_analysis(),
            decisive_claims=_decisive_claims_supported(2),
        )
        assert result.outcome == Outcome.ANALYSIS
        matched = [r for r in result.rule_trace if r["matched"]]
        assert matched[0]["rule"] == "A3"

    def test_a5_unexplored_frames(self):
        """A5: unexplored frames remain -> NO_CONSENSUS."""
        div = DivergenceResult(alt_frames=[
            FrameInfo("F-1", "Frame 1", survival_status=FrameSurvivalStatus.UNEXPLORED),
        ])
        result = run_gate2_deterministic(
            agreement_ratio=0.60,
            positions=_positions(2),
            contradictions=[],
            unaddressed_arguments=[],
            open_blockers=[],
            evidence_count=5,
            search_enabled=True,
            preflight=_preflight_analysis(),
            divergence=div,
        )
        assert result.outcome == Outcome.NO_CONSENSUS
        matched = [r for r in result.rule_trace if r["matched"]]
        assert matched[0]["rule"] == "A5"

    def test_a6_groupthink(self):
        """A6: groupthink_warning -> ESCALATE."""
        result = run_gate2_deterministic(
            agreement_ratio=0.60,
            positions=_positions(2),
            contradictions=[],
            unaddressed_arguments=[],
            open_blockers=[],
            evidence_count=5,
            search_enabled=True,
            preflight=_preflight_analysis(),
            stability=_stability(groupthink_warning=True),
        )
        assert result.outcome == Outcome.ESCALATE
        matched = [r for r in result.rule_trace if r["matched"]]
        assert matched[0]["rule"] == "A6"

    def test_a7_fallback(self):
        """A7: fallback -> ANALYSIS."""
        result = run_gate2_deterministic(
            agreement_ratio=0.60,
            positions=_positions(2),
            contradictions=[],
            unaddressed_arguments=[],
            open_blockers=[],
            evidence_count=5,
            search_enabled=True,
            preflight=_preflight_analysis(),
            stability=_stability(groupthink_warning=False),
        )
        assert result.outcome == Outcome.ANALYSIS
        matched = [r for r in result.rule_trace if r["matched"]]
        assert matched[0]["rule"] == "A7"


# ---------------------------------------------------------------------------
# Rule trace
# ---------------------------------------------------------------------------

class TestRuleTrace:
    """Verify rule_trace is populated correctly."""

    def test_rule_trace_populated(self):
        result = run_gate2_deterministic(
            agreement_ratio=0.80,
            positions=_positions(2),
            contradictions=[],
            unaddressed_arguments=[],
            open_blockers=[],
            evidence_count=5,
            search_enabled=True,
            preflight=_preflight_decide(),
            stability=_stability(conclusion_stable=True),
        )
        assert len(result.rule_trace) > 0
        assert result.rule_trace[0]["rule"] == "D1"
        assert result.rule_trace[0]["matched"] is True

    def test_rule_trace_records_non_matches(self):
        """When D1 doesn't match, it should be recorded as matched=False."""
        result = run_gate2_deterministic(
            agreement_ratio=0.30,
            positions=_positions(2),
            contradictions=[],
            unaddressed_arguments=[],
            open_blockers=[],
            evidence_count=5,
            search_enabled=True,
            preflight=_preflight_decide(stakes_class=StakesClass.STANDARD),
            stability=_stability(),
        )
        d1 = result.rule_trace[0]
        assert d1["rule"] == "D1"
        assert d1["matched"] is False

    def test_modality_in_result(self):
        result = run_gate2_deterministic(
            agreement_ratio=0.80,
            positions=_positions(2),
            contradictions=[],
            unaddressed_arguments=[],
            open_blockers=[],
            evidence_count=5,
            search_enabled=True,
            preflight=_preflight_decide(),
        )
        assert result.modality == "DECIDE"

    def test_analysis_modality_in_result(self):
        result = run_gate2_deterministic(
            agreement_ratio=0.60,
            positions=_positions(2),
            contradictions=[],
            unaddressed_arguments=[],
            open_blockers=[],
            evidence_count=5,
            search_enabled=True,
            preflight=_preflight_analysis(),
        )
        assert result.modality == "ANALYSIS"

    def test_each_rule_entry_has_required_keys(self):
        result = run_gate2_deterministic(
            agreement_ratio=0.80,
            positions=_positions(2),
            contradictions=[],
            unaddressed_arguments=[],
            open_blockers=[],
            evidence_count=5,
            search_enabled=True,
            preflight=_preflight_decide(),
            stability=_stability(conclusion_stable=True),
        )
        for entry in result.rule_trace:
            assert "rule" in entry
            assert "matched" in entry
            assert "reason" in entry
