"""Gate 2: Deterministic trust assessment with D1-D14 and A1-A7 rule sets.

No LLM call. Thresholds on mechanical tool data only.

DECIDE modality: D1-D14 rules, first match wins.
ANALYSIS modality: A1-A7 rules, first match wins.

Every rule evaluated is recorded in rule_trace for auditability.
"""
from __future__ import annotations

from typing import Optional

from thinker.pipeline import pipeline_stage
from thinker.types import (
    Argument, ArgumentStatus, Blocker, Contradiction,
    DecisiveClaim, DimensionSeedResult, DivergenceResult,
    EvidenceSupportStatus, FrameSurvivalStatus,
    Gate2Assessment, Modality, Outcome, Position,
    PreflightResult, StabilityResult,
)


@pipeline_stage(
    name="Gate 2",
    description="Fully deterministic trust assessment. No LLM call. Instant. Reproducible. "
                "D1-D14 (DECIDE) and A1-A7 (ANALYSIS) rule sets, first match wins. "
                "Every rule evaluated is recorded in rule_trace.",
    stage_type="deterministic",
    order=7,
    provider="deterministic (no LLM)",
    inputs=["agreement_ratio", "positions", "contradictions", "unaddressed_arguments",
            "open_blockers", "evidence_count", "search_enabled",
            "preflight", "divergence", "stability", "decisive_claims", "dimensions",
            "total_arguments", "archive_evidence_count"],
    outputs=["outcome (DECIDE/ESCALATE/NO_CONSENSUS/ANALYSIS/ERROR/NEED_MORE)", "rule_trace"],
    logic="""DECIDE modality: D1-D14, first match wins.
ANALYSIS modality: A1-A7, first match wins.
See module docstring for full rule definitions.""",
    thresholds={"agreement_ratio >= 0.75": "DECIDE", "agreement_ratio < 0.5": "NO_CONSENSUS/ESCALATE"},
    failure_mode="Cannot fail — deterministic computation.",
    cost="$0 (no LLM call)",
    stage_id="gate2",
)
def classify_outcome(
    agreement_ratio: float,
    ignored_arguments: int,
    mentioned_arguments: int,
    evidence_count: int,
    contradictions: int,
    open_blockers: int,
    search_enabled: bool,
) -> str:
    """Deterministic outcome classification (V8 compat).

    Returns one of: CONSENSUS, CLOSED_WITH_ACCEPTED_RISKS, PARTIAL_CONSENSUS,
    INSUFFICIENT_EVIDENCE, NO_CONSENSUS.
    """
    if agreement_ratio < 0.5:
        return "NO_CONSENSUS"

    if search_enabled and evidence_count == 0:
        return "INSUFFICIENT_EVIDENCE"

    if (agreement_ratio >= 0.75
            and ignored_arguments == 0
            and contradictions == 0
            and open_blockers == 0):
        return "CONSENSUS"

    if agreement_ratio >= 0.75 and ignored_arguments <= 2:
        return "CLOSED_WITH_ACCEPTED_RISKS"

    return "PARTIAL_CONSENSUS"


# ---------------------------------------------------------------------------
# Helper: blocker severity (backward-compatible)
# ---------------------------------------------------------------------------

def _blocker_severity(b: Blocker) -> str:
    """Get severity from a Blocker, defaulting to LOW if not present."""
    return getattr(b, "severity", "LOW")


def _all_blockers_low(blockers: list[Blocker]) -> bool:
    """True if every blocker has LOW severity (or list is empty)."""
    return all(_blocker_severity(b) == "LOW" for b in blockers)


# ---------------------------------------------------------------------------
# DECIDE rules D1-D14
# ---------------------------------------------------------------------------

def _eval_decide_rules(
    agreement_ratio: float,
    positions: dict[str, Position],
    contradictions: list,
    unaddressed_arguments: list,
    open_blockers: list[Blocker],
    evidence_count: int,
    search_enabled: bool,
    preflight: Optional[PreflightResult],
    divergence: Optional[DivergenceResult],
    stability: Optional[StabilityResult],
    decisive_claims: Optional[list[DecisiveClaim]],
    dimensions: Optional[DimensionSeedResult],
    total_arguments: int,
) -> tuple[Outcome, list[dict]]:
    """Evaluate D1-D14 in order. Returns (outcome, rule_trace)."""
    trace: list[dict] = []

    def _rule(rule_id: str, matched: bool, reason: str) -> bool:
        trace.append({"rule": rule_id, "matched": matched, "reason": reason})
        return matched

    # Unresolved contradictions
    unresolved_contradictions = [
        c for c in contradictions
        if getattr(c, "status", "OPEN") == "OPEN"
    ]

    # Decisive claims support check
    claims_supported = False
    if decisive_claims:
        claims_supported = all(
            c.evidence_support_status in (EvidenceSupportStatus.SUPPORTED, EvidenceSupportStatus.PARTIAL)
            for c in decisive_claims
            if c.material_to_conclusion
        )

    # Material unrebutted frames
    material_unrebutted = 0
    if divergence:
        material_unrebutted = divergence.material_unrebutted_frame_count

    # Dimension coverage gaps
    has_coverage_gaps = False
    if dimensions and dimensions.items:
        has_coverage_gaps = any(
            d.coverage_status == "ZERO" and d.mandatory and not d.justified_irrelevance
            for d in dimensions.items
        )

    # Fatal premise
    has_fatal_premise = preflight.fatal_premise if preflight else False

    # Stability
    conclusion_stable = stability.conclusion_stable if stability else True
    groupthink_warning = stability.groupthink_warning if stability else False

    # Number of models that responded
    models_responded = len(positions)

    # --- D1: High agreement, no blockers, stable ---
    if _rule("D1",
             agreement_ratio >= 0.75 and len(open_blockers) == 0 and conclusion_stable,
             f"agreement={agreement_ratio:.2f}>=0.75, blockers={len(open_blockers)}==0, stable={conclusion_stable}"):
        return Outcome.DECIDE, trace

    # --- D2: High agreement, blockers all LOW severity ---
    if _rule("D2",
             agreement_ratio >= 0.75 and len(open_blockers) > 0 and _all_blockers_low(open_blockers),
             f"agreement={agreement_ratio:.2f}>=0.75, blockers={len(open_blockers)}>0, all_low={_all_blockers_low(open_blockers)}"):
        return Outcome.DECIDE, trace

    # --- D3: High agreement but groupthink warning ---
    if _rule("D3",
             agreement_ratio >= 0.75 and groupthink_warning,
             f"agreement={agreement_ratio:.2f}>=0.75, groupthink_warning={groupthink_warning}"):
        return Outcome.ESCALATE, trace

    # --- D4: Moderate agreement, evidence, decisive claims supported ---
    if _rule("D4",
             agreement_ratio >= 0.50 and evidence_count >= 3 and claims_supported,
             f"agreement={agreement_ratio:.2f}>=0.50, evidence={evidence_count}>=3, claims_supported={claims_supported}"):
        return Outcome.DECIDE, trace

    # --- D5: Moderate agreement, material unrebutted frames ---
    if _rule("D5",
             agreement_ratio >= 0.50 and material_unrebutted > 0,
             f"agreement={agreement_ratio:.2f}>=0.50, material_unrebutted={material_unrebutted}>0"):
        return Outcome.ESCALATE, trace

    # --- D6: Moderate agreement, unresolved contradictions ---
    if _rule("D6",
             agreement_ratio >= 0.50 and len(unresolved_contradictions) > 0,
             f"agreement={agreement_ratio:.2f}>=0.50, unresolved_contradictions={len(unresolved_contradictions)}>0"):
        return Outcome.ESCALATE, trace

    # --- D7: Moderate agreement, no evidence ---
    if _rule("D7",
             agreement_ratio >= 0.50 and evidence_count == 0 and search_enabled,
             f"agreement={agreement_ratio:.2f}>=0.50, evidence={evidence_count}==0, search_enabled={search_enabled}"):
        return Outcome.ESCALATE, trace

    # --- D8: Low agreement, HIGH stakes ---
    high_stakes = preflight and preflight.stakes_class.value == "HIGH" if preflight else False
    if _rule("D8",
             agreement_ratio < 0.50 and high_stakes,
             f"agreement={agreement_ratio:.2f}<0.50, high_stakes={high_stakes}"):
        return Outcome.ESCALATE, trace

    # --- D9: Low agreement, coverage gaps ---
    if _rule("D9",
             agreement_ratio < 0.50 and has_coverage_gaps,
             f"agreement={agreement_ratio:.2f}<0.50, coverage_gaps={has_coverage_gaps}"):
        return Outcome.NO_CONSENSUS, trace

    # --- D10: Low agreement fallback ---
    if _rule("D10",
             agreement_ratio < 0.50,
             f"agreement={agreement_ratio:.2f}<0.50"):
        return Outcome.NO_CONSENSUS, trace

    # --- D11: Fatal premise ---
    if _rule("D11",
             has_fatal_premise,
             f"fatal_premise={has_fatal_premise}"):
        return Outcome.NEED_MORE, trace

    # --- D12: No models responded ---
    if _rule("D12",
             models_responded == 0,
             f"models_responded={models_responded}==0"):
        return Outcome.ERROR, trace

    # --- D13: Zero arguments tracked ---
    if _rule("D13",
             total_arguments == 0,
             f"total_arguments={total_arguments}==0"):
        return Outcome.ERROR, trace

    # --- D14: Fallback ---
    _rule("D14", True, "fallback — no prior rule matched")
    return Outcome.ESCALATE, trace


# ---------------------------------------------------------------------------
# ANALYSIS rules A1-A7
# ---------------------------------------------------------------------------

def _eval_analysis_rules(
    agreement_ratio: float,
    positions: dict[str, Position],
    contradictions: list,
    unaddressed_arguments: list,
    open_blockers: list[Blocker],
    evidence_count: int,
    search_enabled: bool,
    preflight: Optional[PreflightResult],
    divergence: Optional[DivergenceResult],
    stability: Optional[StabilityResult],
    decisive_claims: Optional[list[DecisiveClaim]],
    dimensions: Optional[DimensionSeedResult],
    total_arguments: int,
) -> tuple[Outcome, list[dict]]:
    """Evaluate A1-A7 in order. Returns (outcome, rule_trace)."""
    trace: list[dict] = []

    def _rule(rule_id: str, matched: bool, reason: str) -> bool:
        trace.append({"rule": rule_id, "matched": matched, "reason": reason})
        return matched

    # Dimension coverage
    all_dimensions_explored = False
    dimension_coverage = 0.0
    if dimensions and dimensions.items:
        all_dimensions_explored = all(
            d.coverage_status != "ZERO" or d.justified_irrelevance or not d.mandatory
            for d in dimensions.items
        )
        dimension_coverage = dimensions.dimension_coverage_score

    # Hypothesis ledger = decisive_claims populated
    hypothesis_populated = bool(decisive_claims and len(decisive_claims) > 0)

    # Frame statuses (ANALYSIS mode uses EXPLORED/NOTED/UNEXPLORED)
    frames = divergence.alt_frames if divergence else []
    all_frames_explored = all(
        f.survival_status in (FrameSurvivalStatus.EXPLORED, FrameSurvivalStatus.NOTED)
        for f in frames
    ) if frames else True
    unexplored_frames = [
        f for f in frames
        if f.survival_status == FrameSurvivalStatus.UNEXPLORED
    ]

    groupthink_warning = stability.groupthink_warning if stability else False

    # --- A1: All dimensions explored ---
    if _rule("A1",
             all_dimensions_explored and (not dimensions or len(dimensions.items) > 0),
             f"all_dimensions_explored={all_dimensions_explored}"):
        return Outcome.ANALYSIS, trace

    # --- A2: Low dimension coverage ---
    if _rule("A2",
             dimension_coverage < 0.5 and dimensions is not None and len(dimensions.items) > 0,
             f"dimension_coverage={dimension_coverage:.2f}<0.5"):
        return Outcome.NO_CONSENSUS, trace

    # --- A3: Hypothesis ledger populated ---
    if _rule("A3",
             hypothesis_populated,
             f"hypothesis_populated={hypothesis_populated}"):
        return Outcome.ANALYSIS, trace

    # --- A4: All frames explored/noted ---
    if _rule("A4",
             all_frames_explored and len(frames) > 0,
             f"all_frames_explored={all_frames_explored}, frame_count={len(frames)}"):
        return Outcome.ANALYSIS, trace

    # --- A5: Unexplored frames remain ---
    if _rule("A5",
             len(unexplored_frames) > 0,
             f"unexplored_frames={len(unexplored_frames)}>0"):
        return Outcome.NO_CONSENSUS, trace

    # --- A6: Groupthink warning ---
    if _rule("A6",
             groupthink_warning,
             f"groupthink_warning={groupthink_warning}"):
        return Outcome.ESCALATE, trace

    # --- A7: Fallback ---
    _rule("A7", True, "fallback — ANALYSIS mode default")
    return Outcome.ANALYSIS, trace


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_gate2_deterministic(
    agreement_ratio: float,
    positions: dict[str, Position],
    contradictions: list,
    unaddressed_arguments: list,
    open_blockers: list,
    evidence_count: int,
    search_enabled: bool,
    preflight: Optional[PreflightResult] = None,
    divergence: Optional[DivergenceResult] = None,
    stability: Optional[StabilityResult] = None,
    decisive_claims: Optional[list[DecisiveClaim]] = None,
    dimensions: Optional[DimensionSeedResult] = None,
    total_arguments: int = 0,
    archive_evidence_count: int = 0,
) -> Gate2Assessment:
    """Deterministic Gate 2 — no LLM call.

    Dispatches to D1-D14 (DECIDE modality) or A1-A7 (ANALYSIS modality)
    based on preflight.modality. First matching rule wins.

    All parameters after search_enabled are optional for backward compatibility.
    """
    # Determine modality
    is_analysis = (preflight is not None and preflight.modality == Modality.ANALYSIS)
    modality_label = "ANALYSIS" if is_analysis else "DECIDE"

    # Compute legacy flags for backward-compat fields
    ignored = [a for a in unaddressed_arguments if isinstance(a, Argument) and a.status == ArgumentStatus.IGNORED]
    mentioned = [a for a in unaddressed_arguments if isinstance(a, Argument) and a.status == ArgumentStatus.MENTIONED]

    convergence_ok = agreement_ratio >= 0.75
    evidence_ok = evidence_count >= 3 or not search_enabled
    dissent_ok = len(ignored) <= 2
    data_ok = evidence_count > 0 or not search_enabled
    no_blockers = len(open_blockers) == 0

    # Dispatch to rule engine
    if is_analysis:
        outcome, rule_trace = _eval_analysis_rules(
            agreement_ratio=agreement_ratio,
            positions=positions,
            contradictions=contradictions,
            unaddressed_arguments=unaddressed_arguments,
            open_blockers=open_blockers,
            evidence_count=evidence_count,
            search_enabled=search_enabled,
            preflight=preflight,
            divergence=divergence,
            stability=stability,
            decisive_claims=decisive_claims,
            dimensions=dimensions,
            total_arguments=total_arguments,
        )
    else:
        outcome, rule_trace = _eval_decide_rules(
            agreement_ratio=agreement_ratio,
            positions=positions,
            contradictions=contradictions,
            unaddressed_arguments=unaddressed_arguments,
            open_blockers=open_blockers,
            evidence_count=evidence_count,
            search_enabled=search_enabled,
            preflight=preflight,
            divergence=divergence,
            stability=stability,
            decisive_claims=decisive_claims,
            dimensions=dimensions,
            total_arguments=total_arguments,
        )

    # Identify which rule matched
    matched_rule = next((r["rule"] for r in rule_trace if r["matched"]), "NONE")

    # Build legacy classification for backward compat
    outcome_class = classify_outcome(
        agreement_ratio=agreement_ratio,
        ignored_arguments=len(ignored),
        mentioned_arguments=len(mentioned),
        evidence_count=evidence_count,
        contradictions=len(contradictions),
        open_blockers=len(open_blockers),
        search_enabled=search_enabled,
    )

    return Gate2Assessment(
        outcome=outcome,
        convergence_ok=convergence_ok,
        evidence_credible=evidence_ok,
        dissent_addressed=dissent_ok,
        enough_data=data_ok,
        report_honest=no_blockers,
        reasoning=(
            f"Deterministic [{modality_label}]: rule={matched_rule}, "
            f"agreement={agreement_ratio:.2f}, "
            f"ignored={len(ignored)}, evidence={evidence_count}, "
            f"contradictions={len(contradictions)}, blockers={len(open_blockers)}, "
            f"class={outcome_class}"
        ),
        modality=modality_label,
        rule_trace=rule_trace,
    )
