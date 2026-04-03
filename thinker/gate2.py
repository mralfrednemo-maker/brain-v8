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
    """Evaluate D1-D14 per DOD-V3 Section 16. First match wins."""
    trace: list[dict] = []

    def _t(rule_id: str, matched: bool, reason: str) -> bool:
        trace.append({"rule_id": rule_id, "evaluated": True, "fired": matched,
                      "outcome_if_fired": None, "reason": reason})
        return matched

    # Pre-compute conditions
    stability = stability or StabilityResult()
    conclusion_stable = stability.conclusion_stable
    reason_stable = stability.reason_stable
    assumption_stable = stability.assumption_stable
    groupthink_warning = stability.groupthink_warning
    independent_evidence = stability.independent_evidence_present

    # CRITICAL blockers — any kind with severity CRITICAL (DOD Section 13.1)
    critical_blockers = [b for b in open_blockers
                         if getattr(b, 'severity', 'MEDIUM') in ("HIGH", "CRITICAL")]

    # Decisive claims without valid evidence
    claims_lacking_evidence = [
        c for c in (decisive_claims or [])
        if c.material_to_conclusion and c.evidence_support_status != EvidenceSupportStatus.SUPPORTED
    ]

    # HIGH/CRITICAL unresolved contradictions (handle both enum and string severity)
    high_contradictions = [
        c for c in contradictions
        if getattr(c, "status", "OPEN") in ("OPEN", "open")
        and str(getattr(getattr(c, "severity", "LOW"), "value", getattr(c, "severity", "LOW"))) in ("HIGH", "CRITICAL")
    ]

    # Unresolved CRITICAL premise flags
    critical_premise_flags = preflight.unresolved_critical_flags if preflight else []

    # Material frames without rebuttal or disposition
    material_frames_unresolved = []
    if divergence:
        for f in divergence.alt_frames:
            if (f.material_to_outcome
                    and f.survival_status in (FrameSurvivalStatus.ACTIVE, FrameSurvivalStatus.CONTESTED)
                    and f.synthesis_disposition_status == "UNADDRESSED"):
                material_frames_unresolved.append(f)

    # --- D1: Fatal integrity or infrastructure failure (DOD 3.3) ---
    fatal_integrity = (total_arguments == 0 and len(positions) == 0)
    if _t("D1", fatal_integrity,
          f"models={len(positions)}, args={total_arguments}"):
        trace[-1]["outcome_if_fired"] = "ERROR"
        return Outcome.ERROR, trace

    # --- D2: Modality mismatch ---
    modality_mismatch = preflight and preflight.modality != Modality.DECIDE if preflight else False
    if _t("D2", modality_mismatch,
          f"preflight.modality={preflight.modality.value if preflight else 'N/A'}"):
        trace[-1]["outcome_if_fired"] = "ERROR"
        return Outcome.ERROR, trace

    # --- D3: Illegal SHORT_CIRCUIT state (guardrails violated) ---
    # Deferred per user directive — no budget enforcement
    _t("D3", False, "SHORT_CIRCUIT guardrail check deferred")

    # --- D4: agreement < 0.50 ---
    if _t("D4", agreement_ratio < 0.50,
          f"agreement={agreement_ratio:.2f}<0.50"):
        trace[-1]["outcome_if_fired"] = "NO_CONSENSUS"
        return Outcome.NO_CONSENSUS, trace

    # --- D5: agreement 0.50-0.74 ---
    if _t("D5", 0.50 <= agreement_ratio < 0.75,
          f"agreement={agreement_ratio:.2f} in [0.50,0.75)"):
        trace[-1]["outcome_if_fired"] = "ESCALATE"
        return Outcome.ESCALATE, trace

    # --- D6: Any unresolved CRITICAL blocker ---
    if _t("D6", len(critical_blockers) > 0,
          f"critical_blockers={len(critical_blockers)}"):
        trace[-1]["outcome_if_fired"] = "ESCALATE"
        return Outcome.ESCALATE, trace

    # --- D7: Decisive claim lacks valid evidence binding ---
    if _t("D7", len(claims_lacking_evidence) > 0,
          f"claims_lacking_evidence={len(claims_lacking_evidence)}"):
        trace[-1]["outcome_if_fired"] = "ESCALATE"
        return Outcome.ESCALATE, trace

    # --- D8: HIGH/CRITICAL contradiction unresolved ---
    if _t("D8", len(high_contradictions) > 0,
          f"high_contradictions={len(high_contradictions)}"):
        trace[-1]["outcome_if_fired"] = "ESCALATE"
        return Outcome.ESCALATE, trace

    # --- D9: Unresolved CRITICAL premise flag ---
    if _t("D9", len(critical_premise_flags) > 0,
          f"critical_premise_flags={len(critical_premise_flags)}"):
        trace[-1]["outcome_if_fired"] = "ESCALATE"
        return Outcome.ESCALATE, trace

    # --- D10: Material frame ACTIVE/CONTESTED without disposition ---
    if _t("D10", len(material_frames_unresolved) > 0,
          f"material_frames_unresolved={len(material_frames_unresolved)}"):
        trace[-1]["outcome_if_fired"] = "ESCALATE"
        return Outcome.ESCALATE, trace

    # --- D11: conclusion_stable = false ---
    if _t("D11", not conclusion_stable,
          f"conclusion_stable={conclusion_stable}"):
        trace[-1]["outcome_if_fired"] = "NO_CONSENSUS"
        return Outcome.NO_CONSENSUS, trace

    # --- D12: reason_stable = false OR assumption_stable = false ---
    if _t("D12", not reason_stable or not assumption_stable,
          f"reason_stable={reason_stable}, assumption_stable={assumption_stable}"):
        trace[-1]["outcome_if_fired"] = "ESCALATE"
        return Outcome.ESCALATE, trace

    # --- D13: groupthink + no independent evidence ---
    if _t("D13", groupthink_warning and not independent_evidence,
          f"groupthink={groupthink_warning}, independent_evidence={independent_evidence}"):
        trace[-1]["outcome_if_fired"] = "ESCALATE"
        return Outcome.ESCALATE, trace

    # --- D14: Otherwise → DECIDE ---
    _t("D14", True, "all checks passed")
    trace[-1]["outcome_if_fired"] = "DECIDE"
    return Outcome.DECIDE, trace


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
    archive_evidence_count: int = 0,
) -> tuple[Outcome, list[dict]]:
    """Evaluate A1-A7 per DOD-V3 Section 17. First match wins.

    ANALYSIS mode may only emit: ANALYSIS, ESCALATE, ERROR (never NO_CONSENSUS).
    """
    trace: list[dict] = []

    def _t(rule_id: str, matched: bool, reason: str) -> bool:
        trace.append({"rule_id": rule_id, "evaluated": True, "fired": matched,
                      "outcome_if_fired": None, "reason": reason})
        return matched

    from thinker.types import SearchScope

    # --- A1: Missing or invalid PreflightAssessment ---
    preflight_missing = preflight is None or not preflight.executed or not preflight.parse_ok
    if _t("A1", preflight_missing,
          f"preflight={'missing' if preflight is None else f'executed={preflight.executed}, parse_ok={preflight.parse_ok}'}"):
        trace[-1]["outcome_if_fired"] = "ERROR"
        return Outcome.ERROR, trace

    # --- A2: Modality mismatch ---
    modality_mismatch = preflight.modality != Modality.ANALYSIS if preflight else True
    if _t("A2", modality_mismatch,
          f"preflight.modality={preflight.modality.value if preflight else 'N/A'}"):
        trace[-1]["outcome_if_fired"] = "ERROR"
        return Outcome.ERROR, trace

    # --- A3: Missing required shared pipeline artifacts ---
    missing_artifacts = (
        (dimensions is None or len(dimensions.items) == 0)
        or total_arguments == 0
    )
    if _t("A3", missing_artifacts,
          f"dimensions={'empty' if not dimensions or not dimensions.items else len(dimensions.items)}, args={total_arguments}"):
        trace[-1]["outcome_if_fired"] = "ERROR"
        return Outcome.ERROR, trace

    # --- A4: Evidence archive empty AND search_scope != NONE ---
    search_scope_not_none = preflight.search_scope != SearchScope.NONE if preflight else False
    evidence_archive_empty = archive_evidence_count == 0 and evidence_count == 0
    if _t("A4", evidence_archive_empty and search_scope_not_none,
          f"evidence={evidence_count}, archive={archive_evidence_count}, search_scope={preflight.search_scope.value if preflight else 'N/A'}"):
        trace[-1]["outcome_if_fired"] = "ESCALATE"
        return Outcome.ESCALATE, trace

    # --- A5: Any mandatory dimension has zero arguments ---
    zero_coverage_dims = []
    if dimensions and dimensions.items:
        zero_coverage_dims = [d for d in dimensions.items
                              if d.mandatory and d.coverage_status == "ZERO"
                              and not d.justified_irrelevance]
    if _t("A5", len(zero_coverage_dims) > 0,
          f"zero_coverage_dimensions={len(zero_coverage_dims)}"):
        trace[-1]["outcome_if_fired"] = "ESCALATE"
        return Outcome.ESCALATE, trace

    # --- A6: Total arguments < 8 ---
    if _t("A6", total_arguments < 8,
          f"total_arguments={total_arguments}<8"):
        trace[-1]["outcome_if_fired"] = "ESCALATE"
        return Outcome.ESCALATE, trace

    # --- A7: Otherwise → ANALYSIS ---
    _t("A7", True, "all checks passed — ANALYSIS")
    trace[-1]["outcome_if_fired"] = "ANALYSIS"
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
            archive_evidence_count=archive_evidence_count,
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

    # Identify which rule fired
    matched_rule = next((r["rule_id"] for r in rule_trace if r.get("fired")), "NONE")

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
