"""Tests for Gate 2: deterministic trust assessment with D1-D14 / A1-A7 rule sets.

V9 spec: Gate 2 is fully deterministic. No LLM call.
D1-D14 for DECIDE modality, A1-A7 for ANALYSIS modality.
First matching rule wins. Every rule evaluated is recorded in rule_trace.

Trace schema: {"rule_id": str, "evaluated": bool, "fired": bool, "outcome_if_fired": str|None, "reason": str}
"""
import pytest

from thinker.gate2 import run_gate2_deterministic, classify_outcome
from thinker.types import (
    Argument, ArgumentStatus, Blocker, BlockerKind, BlockerStatus,
    Confidence, Contradiction, DecisiveClaim, DimensionItem,
    DimensionSeedResult, DivergenceResult, EvidenceSupportStatus,
    FrameInfo, FrameSurvivalStatus, FrameType, Modality, Outcome,
    Position, PremiseFlag, PremiseFlagSeverity, PremiseFlagType,
    PreflightResult, SearchScope, StabilityResult, StakesClass,
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
            evidence_refs=[f"E{i+1:03d}"],  # DOD: SUPPORTED must have evidence_refs
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


def _base_decide_kwargs(**overrides):
    """Base keyword arguments for a clean DECIDE path (reaches D14).

    All stability flags True, no blockers, no contradictions, agreement >= 0.75,
    total_arguments > 0, positions > 0. Override specific keys to trigger earlier rules.
    """
    defaults = dict(
        agreement_ratio=0.90,
        positions=_positions(2),
        contradictions=[],
        unaddressed_arguments=[],
        open_blockers=[],
        evidence_count=10,
        search_enabled=True,
        preflight=_preflight_decide(),
        stability=_stability(
            conclusion_stable=True,
            reason_stable=True,
            assumption_stable=True,
            groupthink_warning=False,
            independent_evidence_present=True,
        ),
        divergence=_divergence(0),
        decisive_claims=_decisive_claims_supported(2),
        total_arguments=10,
    )
    defaults.update(overrides)
    return defaults


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
    """Old code calling with just the basic params should still work.

    D1 fires on positions=0 AND total_arguments=0, so backward-compat tests
    must provide positions and total_arguments to avoid hitting D1/ERROR.
    """

    def test_high_agreement_decides(self):
        result = run_gate2_deterministic(
            agreement_ratio=1.0,
            positions=_positions(2),
            contradictions=[],
            unaddressed_arguments=[],
            open_blockers=[],
            evidence_count=10,
            search_enabled=True,
            total_arguments=10,
        )
        assert result.outcome == Outcome.DECIDE
        assert result.convergence_ok is True
        assert result.dissent_addressed is True

    def test_low_agreement_no_consensus(self):
        """DOD D4: agreement < 0.50 -> NO_CONSENSUS."""
        result = run_gate2_deterministic(
            agreement_ratio=0.3,
            positions=_positions(2),
            contradictions=[],
            unaddressed_arguments=[],
            open_blockers=[],
            evidence_count=5,
            search_enabled=True,
            total_arguments=10,
        )
        assert result.outcome == Outcome.NO_CONSENSUS
        assert result.convergence_ok is False

    def test_few_ignored_with_high_agreement_still_decides(self):
        result = run_gate2_deterministic(
            agreement_ratio=1.0,
            positions=_positions(2),
            contradictions=[],
            unaddressed_arguments=[
                Argument("ARG-5", 2, "glm5", "Minor point ignored", status=ArgumentStatus.IGNORED),
            ],
            open_blockers=[],
            evidence_count=10,
            search_enabled=True,
            total_arguments=10,
        )
        assert result.outcome == Outcome.DECIDE

    def test_mentioned_but_not_ignored_decides(self):
        result = run_gate2_deterministic(
            agreement_ratio=1.0,
            positions=_positions(2),
            contradictions=[],
            unaddressed_arguments=[
                Argument("ARG-5", 2, "glm5", "Some point", status=ArgumentStatus.MENTIONED),
            ],
            open_blockers=[],
            evidence_count=10,
            search_enabled=True,
            total_arguments=10,
        )
        assert result.outcome == Outcome.DECIDE

    def test_reasoning_includes_classification(self):
        result = run_gate2_deterministic(
            agreement_ratio=1.0,
            positions=_positions(2),
            contradictions=[],
            unaddressed_arguments=[],
            open_blockers=[],
            evidence_count=10,
            search_enabled=True,
            total_arguments=10,
        )
        assert "class=CONSENSUS" in result.reasoning

    def test_no_search_still_decides(self):
        result = run_gate2_deterministic(
            agreement_ratio=1.0,
            positions=_positions(2),
            contradictions=[],
            unaddressed_arguments=[],
            open_blockers=[],
            evidence_count=0,
            search_enabled=False,
            total_arguments=10,
        )
        assert result.outcome == Outcome.DECIDE
        assert result.evidence_credible is True


# ---------------------------------------------------------------------------
# DECIDE rules D1-D14
# ---------------------------------------------------------------------------

class TestDecideRules:
    """D1-D14 rule evaluation for DECIDE modality. One test per rule."""

    def test_d1_fatal_integrity(self):
        """D1: positions=0 AND total_arguments=0 -> ERROR."""
        result = run_gate2_deterministic(
            agreement_ratio=0.90,
            positions={},
            contradictions=[],
            unaddressed_arguments=[],
            open_blockers=[],
            evidence_count=10,
            search_enabled=True,
            preflight=_preflight_decide(),
            total_arguments=0,
        )
        assert result.outcome == Outcome.ERROR
        fired = [r for r in result.rule_trace if r["fired"]]
        assert fired[0]["rule_id"] == "D1"
        assert fired[0]["outcome_if_fired"] == "ERROR"

    def test_d2_modality_mismatch(self):
        """D2: preflight.modality != DECIDE -> ERROR.

        run_gate2_deterministic dispatches based on preflight.modality,
        so an ANALYSIS preflight would go to the A-rules path. We test
        _eval_decide_rules directly to exercise D2.
        """
        from thinker.gate2 import _eval_decide_rules
        outcome, trace = _eval_decide_rules(
            agreement_ratio=0.90,
            positions=_positions(2),
            contradictions=[],
            unaddressed_arguments=[],
            open_blockers=[],
            evidence_count=10,
            search_enabled=True,
            preflight=_preflight_analysis(),  # ANALYSIS modality in DECIDE eval
            divergence=None,
            stability=None,
            decisive_claims=None,
            dimensions=None,
            total_arguments=10,
        )
        assert outcome == Outcome.ERROR
        fired = [r for r in trace if r["fired"]]
        assert fired[0]["rule_id"] == "D2"
        assert fired[0]["outcome_if_fired"] == "ERROR"

    def test_d3_short_circuit_deferred(self):
        """D3: SHORT_CIRCUIT guardrail -- always False (deferred)."""
        result = run_gate2_deterministic(**_base_decide_kwargs())
        d3 = next(r for r in result.rule_trace if r["rule_id"] == "D3")
        assert d3["evaluated"] is True
        assert d3["fired"] is False

    def test_d4_low_agreement(self):
        """D4: agreement < 0.50 -> NO_CONSENSUS."""
        result = run_gate2_deterministic(
            **_base_decide_kwargs(agreement_ratio=0.40),
        )
        assert result.outcome == Outcome.NO_CONSENSUS
        fired = [r for r in result.rule_trace if r["fired"]]
        assert fired[0]["rule_id"] == "D4"
        assert fired[0]["outcome_if_fired"] == "NO_CONSENSUS"

    def test_d5_moderate_agreement(self):
        """D5: agreement 0.50-0.74 -> ESCALATE."""
        result = run_gate2_deterministic(
            **_base_decide_kwargs(agreement_ratio=0.60),
        )
        assert result.outcome == Outcome.ESCALATE
        fired = [r for r in result.rule_trace if r["fired"]]
        assert fired[0]["rule_id"] == "D5"
        assert fired[0]["outcome_if_fired"] == "ESCALATE"

    def test_d6_critical_blockers(self):
        """D6: CRITICAL blockers (COVERAGE_GAP/UNVERIFIED_CLAIM/CONTRADICTION) -> ESCALATE."""
        blocker = Blocker(
            "B-1", BlockerKind.COVERAGE_GAP, "r1", 2,
            status=BlockerStatus.OPEN, severity="CRITICAL",
        )
        result = run_gate2_deterministic(
            **_base_decide_kwargs(open_blockers=[blocker]),
        )
        assert result.outcome == Outcome.ESCALATE
        fired = [r for r in result.rule_trace if r["fired"]]
        assert fired[0]["rule_id"] == "D6"
        assert fired[0]["outcome_if_fired"] == "ESCALATE"

    def test_d7_decisive_claim_lacks_evidence(self):
        """D7: decisive claim material but UNSUPPORTED -> ESCALATE."""
        result = run_gate2_deterministic(
            **_base_decide_kwargs(
                decisive_claims=_decisive_claims_unsupported(1),
            ),
        )
        assert result.outcome == Outcome.ESCALATE
        fired = [r for r in result.rule_trace if r["fired"]]
        assert fired[0]["rule_id"] == "D7"
        assert fired[0]["outcome_if_fired"] == "ESCALATE"

    def test_d8_high_contradiction(self):
        """D8: HIGH/CRITICAL unresolved contradiction -> ESCALATE."""
        ctr = Contradiction("CTR-1", ["E-1", "E-2"], "topic", "HIGH", status="OPEN")
        result = run_gate2_deterministic(
            **_base_decide_kwargs(contradictions=[ctr]),
        )
        assert result.outcome == Outcome.ESCALATE
        fired = [r for r in result.rule_trace if r["fired"]]
        assert fired[0]["rule_id"] == "D8"
        assert fired[0]["outcome_if_fired"] == "ESCALATE"

    def test_d9_critical_premise_flags(self):
        """D9: CRITICAL premise flags unresolved -> ESCALATE."""
        pf = PremiseFlag(
            flag_id="PF-1",
            flag_type=PremiseFlagType.UNSUPPORTED_ASSUMPTION,
            severity=PremiseFlagSeverity.CRITICAL,
            summary="Critical assumption unverified",
            resolved=False,
        )
        result = run_gate2_deterministic(
            **_base_decide_kwargs(
                preflight=_preflight_decide(premise_flags=[pf]),
            ),
        )
        assert result.outcome == Outcome.ESCALATE
        fired = [r for r in result.rule_trace if r["fired"]]
        assert fired[0]["rule_id"] == "D9"
        assert fired[0]["outcome_if_fired"] == "ESCALATE"

    def test_d10_material_frames_unresolved(self):
        """D10: material frames ACTIVE/CONTESTED without disposition -> ESCALATE."""
        result = run_gate2_deterministic(
            **_base_decide_kwargs(
                divergence=_divergence(material_unrebutted=2),
            ),
        )
        assert result.outcome == Outcome.ESCALATE
        fired = [r for r in result.rule_trace if r["fired"]]
        assert fired[0]["rule_id"] == "D10"
        assert fired[0]["outcome_if_fired"] == "ESCALATE"

    def test_d11_conclusion_unstable(self):
        """D11: conclusion_stable=false -> NO_CONSENSUS."""
        result = run_gate2_deterministic(
            **_base_decide_kwargs(
                stability=_stability(
                    conclusion_stable=False,
                    reason_stable=True,
                    assumption_stable=True,
                ),
            ),
        )
        assert result.outcome == Outcome.NO_CONSENSUS
        fired = [r for r in result.rule_trace if r["fired"]]
        assert fired[0]["rule_id"] == "D11"
        assert fired[0]["outcome_if_fired"] == "NO_CONSENSUS"

    def test_d12_reason_unstable(self):
        """D12: reason_stable=false -> ESCALATE."""
        result = run_gate2_deterministic(
            **_base_decide_kwargs(
                stability=_stability(
                    conclusion_stable=True,
                    reason_stable=False,
                    assumption_stable=True,
                ),
            ),
        )
        assert result.outcome == Outcome.ESCALATE
        fired = [r for r in result.rule_trace if r["fired"]]
        assert fired[0]["rule_id"] == "D12"
        assert fired[0]["outcome_if_fired"] == "ESCALATE"

    def test_d12_assumption_unstable(self):
        """D12 variant: assumption_stable=false -> ESCALATE."""
        result = run_gate2_deterministic(
            **_base_decide_kwargs(
                stability=_stability(
                    conclusion_stable=True,
                    reason_stable=True,
                    assumption_stable=False,
                ),
            ),
        )
        assert result.outcome == Outcome.ESCALATE
        fired = [r for r in result.rule_trace if r["fired"]]
        assert fired[0]["rule_id"] == "D12"

    def test_d13_groupthink_no_independent_evidence(self):
        """D13: groupthink + no independent evidence -> ESCALATE."""
        result = run_gate2_deterministic(
            **_base_decide_kwargs(
                stability=_stability(
                    conclusion_stable=True,
                    reason_stable=True,
                    assumption_stable=True,
                    groupthink_warning=True,
                    independent_evidence_present=False,
                ),
            ),
        )
        assert result.outcome == Outcome.ESCALATE
        fired = [r for r in result.rule_trace if r["fired"]]
        assert fired[0]["rule_id"] == "D13"
        assert fired[0]["outcome_if_fired"] == "ESCALATE"

    def test_d14_otherwise_decide(self):
        """D14: all checks passed -> DECIDE."""
        result = run_gate2_deterministic(**_base_decide_kwargs())
        assert result.outcome == Outcome.DECIDE
        fired = [r for r in result.rule_trace if r["fired"]]
        # D3 always evaluates as fired=False, D14 is the first that fires True
        fired_true = [r for r in fired if r["fired"]]
        assert fired_true[-1]["rule_id"] == "D14"
        assert fired_true[-1]["outcome_if_fired"] == "DECIDE"


# ---------------------------------------------------------------------------
# ANALYSIS rules A1-A7
# ---------------------------------------------------------------------------

def _base_analysis_kwargs(**overrides):
    """Base keyword arguments for a clean ANALYSIS path (reaches A7).

    Valid preflight (ANALYSIS), dimensions with coverage, total_arguments >= 8.
    """
    defaults = dict(
        agreement_ratio=0.60,
        positions=_positions(2),
        contradictions=[],
        unaddressed_arguments=[],
        open_blockers=[],
        evidence_count=5,
        search_enabled=True,
        preflight=_preflight_analysis(),
        stability=_stability(),
        dimensions=_dimensions(
            items=[
                DimensionItem("DIM-1", "Economics", mandatory=True, coverage_status="SATISFIED"),
                DimensionItem("DIM-2", "Ethics", mandatory=True, coverage_status="PARTIAL"),
            ],
            coverage=0.8,
        ),
        total_arguments=10,
        archive_evidence_count=0,
    )
    defaults.update(overrides)
    return defaults


class TestAnalysisRules:
    """A1-A7 rule evaluation for ANALYSIS modality. One test per rule."""

    def test_a1_missing_preflight(self):
        """A1: preflight missing -> ERROR."""
        result = run_gate2_deterministic(
            **_base_analysis_kwargs(preflight=None),
        )
        # With preflight=None, dispatch goes to DECIDE path (not ANALYSIS).
        # A1 is only reachable on the ANALYSIS path, so we force it by setting
        # preflight to one with executed=False but modality=ANALYSIS.
        pf = PreflightResult(modality=Modality.ANALYSIS, executed=False, parse_ok=True)
        result = run_gate2_deterministic(
            **_base_analysis_kwargs(preflight=pf),
        )
        assert result.outcome == Outcome.ERROR
        fired = [r for r in result.rule_trace if r["fired"]]
        assert fired[0]["rule_id"] == "A1"
        assert fired[0]["outcome_if_fired"] == "ERROR"

    def test_a2_modality_mismatch(self):
        """A2: preflight.modality != ANALYSIS -> ERROR."""
        # Feed a DECIDE preflight but force the ANALYSIS code path by
        # setting modality=ANALYSIS then overriding to DECIDE afterward.
        # Actually, the dispatch checks preflight.modality == ANALYSIS to enter
        # the analysis path. To reach A2, we need a preflight that IS dispatched
        # to analysis but whose modality doesn't match ANALYSIS.
        # This is impossible via run_gate2_deterministic since the dispatch
        # checks `preflight.modality == ANALYSIS`. A2 is a guard for future
        # code changes. We test _eval_analysis_rules directly.
        from thinker.gate2 import _eval_analysis_rules
        outcome, trace = _eval_analysis_rules(
            agreement_ratio=0.60,
            positions=_positions(2),
            contradictions=[],
            unaddressed_arguments=[],
            open_blockers=[],
            evidence_count=5,
            search_enabled=True,
            preflight=_preflight_decide(),  # DECIDE modality, but in ANALYSIS eval
            divergence=None,
            stability=None,
            decisive_claims=None,
            dimensions=_dimensions(
                items=[DimensionItem("DIM-1", "X", mandatory=True, coverage_status="SATISFIED")],
            ),
            total_arguments=10,
        )
        assert outcome == Outcome.ERROR
        fired = [r for r in trace if r["fired"]]
        assert fired[0]["rule_id"] == "A2"
        assert fired[0]["outcome_if_fired"] == "ERROR"

    def test_a3_missing_artifacts(self):
        """A3: dimensions empty or total_arguments=0 -> ERROR."""
        result = run_gate2_deterministic(
            **_base_analysis_kwargs(
                dimensions=_dimensions(items=[], coverage=0.0),
                total_arguments=0,
            ),
        )
        assert result.outcome == Outcome.ERROR
        fired = [r for r in result.rule_trace if r["fired"]]
        assert fired[0]["rule_id"] == "A3"
        assert fired[0]["outcome_if_fired"] == "ERROR"

    def test_a4_evidence_empty_search_not_none(self):
        """A4: evidence empty AND search_scope != NONE -> ESCALATE."""
        result = run_gate2_deterministic(
            **_base_analysis_kwargs(
                evidence_count=0,
                archive_evidence_count=0,
                preflight=_preflight_analysis(search_scope=SearchScope.TARGETED),
            ),
        )
        assert result.outcome == Outcome.ESCALATE
        fired = [r for r in result.rule_trace if r["fired"]]
        assert fired[0]["rule_id"] == "A4"
        assert fired[0]["outcome_if_fired"] == "ESCALATE"

    def test_a5_zero_coverage_dimension(self):
        """A5: mandatory dimension with zero coverage -> ESCALATE."""
        dims = _dimensions(
            items=[
                DimensionItem("DIM-1", "Economics", mandatory=True, coverage_status="ZERO"),
                DimensionItem("DIM-2", "Ethics", mandatory=True, coverage_status="SATISFIED"),
            ],
            coverage=0.5,
        )
        result = run_gate2_deterministic(
            **_base_analysis_kwargs(dimensions=dims),
        )
        assert result.outcome == Outcome.ESCALATE
        fired = [r for r in result.rule_trace if r["fired"]]
        assert fired[0]["rule_id"] == "A5"
        assert fired[0]["outcome_if_fired"] == "ESCALATE"

    def test_a6_total_arguments_less_than_8(self):
        """A6: total_arguments < 8 -> ESCALATE."""
        result = run_gate2_deterministic(
            **_base_analysis_kwargs(total_arguments=5),
        )
        assert result.outcome == Outcome.ESCALATE
        fired = [r for r in result.rule_trace if r["fired"]]
        assert fired[0]["rule_id"] == "A6"
        assert fired[0]["outcome_if_fired"] == "ESCALATE"

    def test_a7_otherwise_analysis(self):
        """A7: all checks passed -> ANALYSIS."""
        result = run_gate2_deterministic(**_base_analysis_kwargs())
        assert result.outcome == Outcome.ANALYSIS
        fired = [r for r in result.rule_trace if r["fired"]]
        assert fired[-1]["rule_id"] == "A7"
        assert fired[-1]["outcome_if_fired"] == "ANALYSIS"


# ---------------------------------------------------------------------------
# Rule trace
# ---------------------------------------------------------------------------

class TestRuleTrace:
    """Verify rule_trace uses new schema keys and is populated correctly."""

    def test_rule_trace_populated(self):
        result = run_gate2_deterministic(**_base_decide_kwargs())
        assert len(result.rule_trace) > 0
        # D14 should be the last fired rule for a clean path
        fired = [r for r in result.rule_trace if r["fired"]]
        assert fired[-1]["rule_id"] == "D14"
        assert fired[-1]["fired"] is True

    def test_rule_trace_records_non_matches(self):
        """When a rule doesn't match, it is recorded as fired=False."""
        result = run_gate2_deterministic(
            **_base_decide_kwargs(agreement_ratio=0.40),
        )
        # D1 should not fire (we have positions and args)
        d1 = result.rule_trace[0]
        assert d1["rule_id"] == "D1"
        assert d1["fired"] is False

    def test_modality_in_result(self):
        result = run_gate2_deterministic(**_base_decide_kwargs())
        assert result.modality == "DECIDE"

    def test_analysis_modality_in_result(self):
        result = run_gate2_deterministic(**_base_analysis_kwargs())
        assert result.modality == "ANALYSIS"

    def test_each_rule_entry_has_required_keys(self):
        """New trace schema: rule_id, evaluated, fired, outcome_if_fired, reason."""
        result = run_gate2_deterministic(**_base_decide_kwargs())
        for entry in result.rule_trace:
            assert "rule_id" in entry
            assert "evaluated" in entry
            assert "fired" in entry
            assert "outcome_if_fired" in entry
            assert "reason" in entry

    def test_fired_rule_has_outcome(self):
        """The rule that fired must have a non-None outcome_if_fired."""
        result = run_gate2_deterministic(**_base_decide_kwargs())
        fired = [r for r in result.rule_trace if r["fired"]]
        assert len(fired) > 0
        for r in fired:
            assert r["outcome_if_fired"] is not None


class TestGate2Determinism:
    """DOD §20: Same proof state twice → same Gate 2 result."""

    def test_same_input_same_output(self):
        """Gate 2 is deterministic: identical inputs produce identical outputs."""
        kwargs = _base_decide_kwargs()
        result1 = run_gate2_deterministic(**kwargs)
        result2 = run_gate2_deterministic(**kwargs)
        assert result1.outcome == result2.outcome
        assert len(result1.rule_trace) == len(result2.rule_trace)
        for r1, r2 in zip(result1.rule_trace, result2.rule_trace):
            assert r1["rule_id"] == r2["rule_id"]
            assert r1["fired"] == r2["fired"]

    def test_determinism_with_blockers(self):
        """Determinism holds even with complex blocker state."""
        kwargs = _base_decide_kwargs()
        kwargs["open_blockers"] = [
            Blocker("BLK001", BlockerKind.COVERAGE_GAP, "dim:DIM-1", 3,
                    severity="CRITICAL", detail="test"),
        ]
        result1 = run_gate2_deterministic(**kwargs)
        result2 = run_gate2_deterministic(**kwargs)
        assert result1.outcome == result2.outcome
