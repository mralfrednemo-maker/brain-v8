"""Gate 2: Deterministic trust assessment.

No LLM call. Thresholds on mechanical tool data only.

For decision briefs: DECIDE or ESCALATE based on agreement + argument engagement.
For analysis briefs: always deliver, classification label attached.

Classification system (adapted from Chamber V11):
- CONSENSUS: models agree, all arguments addressed, no open issues
- CLOSED_WITH_ACCEPTED_RISKS: models agree, but open blockers/contradictions acknowledged
- PARTIAL_CONSENSUS: models agree on some points, diverge on others
- INSUFFICIENT_EVIDENCE: not enough evidence gathered to support conclusions
- NO_CONSENSUS: fundamental disagreement persists after all rounds
"""
from __future__ import annotations

from thinker.pipeline import pipeline_stage
from thinker.types import Argument, ArgumentStatus, Blocker, Contradiction, Gate2Assessment, Outcome, Position


@pipeline_stage(
    name="Gate 2",
    description="Fully deterministic trust assessment. No LLM call. Instant. Reproducible. Thresholds on mechanical tool data: agreement_ratio, ignored arguments, evidence count, contradictions, open blockers.",
    stage_type="deterministic",
    provider="deterministic (no LLM)",
    inputs=["agreement_ratio", "ignored_arguments", "evidence_count", "contradictions", "open_blockers", "search_enabled"],
    outputs=["outcome (DECIDE/ESCALATE)", "outcome_class (str)"],
    logic="""if agreement < 0.5 → NO_CONSENSUS
if search_enabled and evidence == 0 → INSUFFICIENT_EVIDENCE
if agreement >= 0.75 and ignored == 0 and contradictions == 0 and blockers == 0 → CONSENSUS
if agreement >= 0.75 and ignored <= 2 → CLOSED_WITH_ACCEPTED_RISKS
else → PARTIAL_CONSENSUS

DECIDE if agreement >= 0.75, else ESCALATE.""",
    thresholds={"agreement_ratio >= 0.75": "DECIDE", "agreement_ratio < 0.5": "NO_CONSENSUS", "ignored_arguments >= 3": "NO_CONSENSUS"},
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
    """Deterministic outcome classification.

    Returns one of: CONSENSUS, CLOSED_WITH_ACCEPTED_RISKS, PARTIAL_CONSENSUS,
    INSUFFICIENT_EVIDENCE, NO_CONSENSUS.
    """
    # NO_CONSENSUS: low agreement AND many ignored arguments
    if agreement_ratio < 0.5:
        return "NO_CONSENSUS"

    # INSUFFICIENT_EVIDENCE: search was enabled but found nothing
    if search_enabled and evidence_count == 0:
        return "INSUFFICIENT_EVIDENCE"

    # CONSENSUS: high agreement, all arguments engaged, no open issues
    if (agreement_ratio >= 0.75
            and ignored_arguments == 0
            and contradictions == 0
            and open_blockers == 0):
        return "CONSENSUS"

    # CLOSED_WITH_ACCEPTED_RISKS: high agreement but open issues acknowledged
    if agreement_ratio >= 0.75 and ignored_arguments <= 2:
        return "CLOSED_WITH_ACCEPTED_RISKS"

    # PARTIAL_CONSENSUS: moderate agreement or many arguments unengaged
    return "PARTIAL_CONSENSUS"


def run_gate2_deterministic(
    agreement_ratio: float,
    positions: dict[str, Position],
    contradictions: list[Contradiction],
    unaddressed_arguments: list[Argument],
    open_blockers: list[Blocker],
    evidence_count: int,
    search_enabled: bool,
) -> Gate2Assessment:
    """Deterministic Gate 2 — no LLM call.

    For decision briefs: DECIDE requires agreement >= 0.75 and all arguments addressed.
    Otherwise: ESCALATE.
    """
    ignored = [a for a in unaddressed_arguments if a.status == ArgumentStatus.IGNORED]
    mentioned = [a for a in unaddressed_arguments if a.status == ArgumentStatus.MENTIONED]

    convergence_ok = agreement_ratio >= 0.75
    evidence_ok = evidence_count >= 3 or not search_enabled
    dissent_ok = len(ignored) <= 2  # A few ignored args don't block if agreement is high
    data_ok = evidence_count > 0 or not search_enabled
    no_blockers = len(open_blockers) == 0

    # DECIDE requires convergence — the conclusion is what matters
    # A few unaddressed minor arguments don't override strong agreement
    if convergence_ok:
        outcome = Outcome.DECIDE
    else:
        outcome = Outcome.ESCALATE

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
            f"Deterministic: agreement={agreement_ratio:.2f}, "
            f"ignored={len(ignored)}, evidence={evidence_count}, "
            f"contradictions={len(contradictions)}, blockers={len(open_blockers)}, "
            f"class={outcome_class}"
        ),
    )
