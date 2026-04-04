"""Stability Tests — deterministic computation (DoD v3.0 Section 15).

No LLM calls. Three booleans: conclusion_stable, reason_stable, assumption_stable.
Plus: fast_consensus_observed, groupthink_warning, independent_evidence_present.
"""
from __future__ import annotations

from thinker.types import (
    CriticalAssumption, DecisiveClaim, Position, QuestionClass,
    StabilityResult, StakesClass,
)


def compute_conclusion_stability(positions: dict[str, Position]) -> bool:
    """Do surviving models agree on the primary recommendation?

    Stable = all models with positions share the same primary_option.
    """
    if not positions:
        return False

    options = set()
    for p in positions.values():
        if p.primary_option:
            options.add(p.primary_option.lower().strip())

    return len(options) <= 1


def compute_reason_stability(
    positions: dict[str, Position],
    decisive_claims: list[DecisiveClaim],
) -> bool:
    """Do models converge for the same reasons? (DOD §15.2)

    Stable = models share the same decisive claim set AND all material
    claims are evidence-supported. If model attribution is available
    (supporting_model_ids), checks that surviving models share claims.
    """
    if not decisive_claims:
        return False

    material_claims = [c for c in decisive_claims if c.material_to_conclusion]
    if not material_claims:
        return False

    # All material claims must be evidence-supported
    if not all(c.evidence_support_status.value == "SUPPORTED" for c in material_claims):
        return False

    # If model attribution is available, check that surviving models share claims
    # DOD §15.2: "Models converge for the same reasons (shared decisive claim set)"
    surviving_models = set(positions.keys()) if positions else set()
    if surviving_models and any(c.supporting_model_ids for c in material_claims):
        # Each surviving model must support at least one material claim
        for model in surviving_models:
            model_supports = any(
                model in c.supporting_model_ids for c in material_claims
            )
            if not model_supports:
                return False  # This model doesn't share any decisive claim

    return True


def compute_assumption_stability(assumptions: list[CriticalAssumption]) -> bool:
    """Are we relying on unresolved material assumptions?

    Stable = no unresolved material assumptions with UNVERIFIABLE/FALSE verifiability.
    """
    if not assumptions:
        return True

    for a in assumptions:
        if (a.material and not a.resolved
                and a.verifiability.value in ("UNVERIFIABLE", "FALSE")):
            return False
    return True


def detect_fast_consensus(
    round_positions: dict[int, dict[str, Position]],
) -> bool:
    """Detect if models agreed too quickly (from R1).

    DOD §15.1: fast_consensus_observed = true if R1 agreement_ratio >= 0.95.
    Agreement ratio = (count of most common option) / total models.
    """
    r1_positions = round_positions.get(1, {})
    if not r1_positions or len(r1_positions) < 2:
        return False

    options: list[str] = []
    for p in r1_positions.values():
        if p.primary_option:
            options.append(p.primary_option.lower().strip())

    if not options:
        return False

    from collections import Counter
    counts = Counter(options)
    most_common_count = counts.most_common(1)[0][1]
    agreement_ratio = most_common_count / len(options)
    return agreement_ratio >= 0.95


def compute_groupthink_warning(
    fast_consensus: bool,
    question_class: QuestionClass,
    stakes_class: StakesClass,
    independent_evidence_present: bool,
) -> bool:
    """Groupthink warning if fast consensus on non-trivial questions.

    Warning if: fast_consensus AND (OPEN/AMBIGUOUS OR HIGH stakes) AND no independent evidence.
    """
    if not fast_consensus:
        return False

    non_trivial = question_class in (QuestionClass.OPEN, QuestionClass.AMBIGUOUS)
    high_stakes = stakes_class == StakesClass.HIGH

    if not (non_trivial or high_stakes):
        return False

    # Independent evidence mitigates groupthink concern
    if independent_evidence_present:
        return False

    return True


def run_stability_tests(
    positions: dict[str, Position],
    decisive_claims: list[DecisiveClaim],
    assumptions: list[CriticalAssumption],
    round_positions: dict[int, dict[str, Position]],
    question_class: QuestionClass,
    stakes_class: StakesClass,
    independent_evidence_present: bool = False,
) -> StabilityResult:
    """Run all stability tests. Returns StabilityResult."""
    conclusion_stable = compute_conclusion_stability(positions)
    reason_stable = compute_reason_stability(positions, decisive_claims)
    assumption_stable = compute_assumption_stability(assumptions)
    fast_consensus = detect_fast_consensus(round_positions)
    groupthink = compute_groupthink_warning(
        fast_consensus, question_class, stakes_class, independent_evidence_present,
    )

    return StabilityResult(
        conclusion_stable=conclusion_stable,
        reason_stable=reason_stable,
        assumption_stable=assumption_stable,
        independent_evidence_present=independent_evidence_present,
        fast_consensus_observed=fast_consensus,
        groupthink_warning=groupthink,
    )
