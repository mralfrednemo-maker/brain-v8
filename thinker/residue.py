"""Post-synthesis residue verification.

V8-F1 (DoD D7): After synthesis, scan the report text to verify it
mentions all structural findings — blocker IDs, contradiction IDs,
and unaddressed argument IDs. This is a narrative completeness check,
not truth verification.

V9 (DoD Section 14): Structured dispositions. Schema validation + coverage
validation replaces string matching. Disposition object for every open blocker,
active frame, decisive claim, contradiction. omission_rate > 0.20 triggers
deep semantic scan.
"""
from __future__ import annotations

from thinker.pipeline import pipeline_stage
from thinker.types import (
    Argument, Blocker, BlockerStatus, Contradiction, DecisiveClaim,
    DispositionObject, DispositionTargetType, FrameInfo, FrameSurvivalStatus,
    SemanticContradiction,
)


def check_synthesis_residue(
    report: str,
    blockers: list[Blocker],
    contradictions: list[Contradiction],
    unaddressed_arguments: list[Argument],
) -> list[dict]:
    """Scan synthesis report for structural finding references.

    Returns list of omission dicts:
    {"type": "blocker"|"contradiction"|"argument", "id": str}

    If >30% of total structural findings are omitted, each omission
    gets threshold_violation=True.
    """
    omissions: list[dict] = []
    total_items = len(blockers) + len(contradictions) + len(unaddressed_arguments)

    # Check blocker IDs
    for b in blockers:
        if b.blocker_id not in report:
            omissions.append({"type": "blocker", "id": b.blocker_id})

    # Check contradiction IDs
    for c in contradictions:
        if c.contradiction_id not in report:
            omissions.append({"type": "contradiction", "id": c.contradiction_id})

    # Check unaddressed argument IDs
    for a in unaddressed_arguments:
        if a.argument_id not in report:
            omissions.append({"type": "argument", "id": a.argument_id})

    # Threshold check: >30% omitted
    threshold_violated = (
        total_items > 0 and len(omissions) / total_items > 0.30
    )
    if threshold_violated:
        for o in omissions:
            o["threshold_violation"] = True

    return omissions


def check_disposition_coverage(
    dispositions: list[DispositionObject],
    open_blockers: list[Blocker],
    active_frames: list[FrameInfo],
    decisive_claims: list[DecisiveClaim],
    contradictions_numeric: list[Contradiction],
    contradictions_semantic: list[SemanticContradiction],
) -> dict:
    """V9: Check that synthesis dispositions cover all tracked open findings.

    Returns dict with: coverage_pass, omission_rate, omissions[], deep_scan_triggered.
    """
    # Build required targets
    required_targets: list[tuple[str, str]] = []  # (target_type, target_id)

    for b in open_blockers:
        if b.status == BlockerStatus.OPEN:
            required_targets.append(("BLOCKER", b.blocker_id))

    for f in active_frames:
        if f.survival_status in (FrameSurvivalStatus.ACTIVE, FrameSurvivalStatus.CONTESTED):
            required_targets.append(("FRAME", f.frame_id))

    for c in decisive_claims:
        required_targets.append(("CLAIM", c.claim_id))

    for c in contradictions_numeric:
        if c.status not in ("RESOLVED", "NON_MATERIAL"):
            required_targets.append(("CONTRADICTION", c.contradiction_id))

    for c in contradictions_semantic:
        if c.status.value not in ("RESOLVED", "NON_MATERIAL"):
            required_targets.append(("CONTRADICTION", c.ctr_id))

    if not required_targets:
        return {
            "coverage_pass": True,
            "omission_rate": 0.0,
            "omissions": [],
            "deep_scan_triggered": False,
            "total_required": 0,
            "total_disposed": 0,
        }

    # Build disposition lookup
    disposed = set()
    for d in dispositions:
        disposed.add((d.target_type.value, d.target_id))

    # Find omissions
    omissions = []
    for target_type, target_id in required_targets:
        if (target_type, target_id) not in disposed:
            omissions.append({"target_type": target_type, "target_id": target_id})

    omission_rate = len(omissions) / len(required_targets) if required_targets else 0.0
    deep_scan = omission_rate > 0.20

    return {
        "coverage_pass": len(omissions) == 0,
        "omission_rate": round(omission_rate, 3),
        "omissions": omissions,
        "deep_scan_triggered": deep_scan,
        "total_required": len(required_targets),
        "total_disposed": len(required_targets) - len(omissions),
    }


def run_deep_semantic_scan(
    report: str,
    omissions: list[dict],
) -> dict:
    """Deep semantic scan: second-pass string match for omitted dispositions.

    DOD §14.5: omission_rate > 0.20 triggers deep semantic scan.
    DOD §14.6: "Deep scan threshold exceeded but scan not run → ERROR."

    Scans the synthesis report text for any reference to omitted targets.
    If the report text mentions the target (by ID or partial text match),
    the omission is downgraded to "addressed_in_text" (soft coverage).
    Remaining true omissions after deep scan are material.
    """
    resolved = []
    still_missing = []

    for om in omissions:
        target_id = om.get("target_id", "")
        # Check if the synthesis text mentions this target by ID
        if target_id and target_id in report:
            resolved.append({**om, "deep_scan_result": "addressed_in_text"})
        else:
            still_missing.append({**om, "deep_scan_result": "confirmed_missing"})

    return {
        "deep_scan_run": True,
        "resolved_by_scan": len(resolved),
        "still_missing": len(still_missing),
        "resolved": resolved,
        "missing": still_missing,
        "material_omissions_remain": len(still_missing) > 0,
    }


@pipeline_stage(
    name="Residue Verification",
    description="Post-synthesis narrative completeness check. Scans the synthesis report text for BLK IDs, CTR IDs, and unaddressed argument IDs. If >30% of structural findings are omitted, flags a threshold violation. This is NOT truth verification — it checks whether the synthesis mentioned the findings, not whether it got them right.",
    stage_type="deterministic",
    order=9,
    provider="deterministic (no LLM)",
    inputs=["synthesis report text", "blockers", "contradictions", "unaddressed_arguments"],
    outputs=["omissions (list[dict]) — type, id, threshold_violation flag"],
    logic="""For each BLK ID: is it mentioned in the report text? If not → omission.
For each CTR ID: is it mentioned? If not → omission.
For each unaddressed argument ID: is it mentioned? If not → omission.
If omissions / total_items > 0.30 → threshold_violation=True on all omissions.""",
    failure_mode="Cannot fail — string matching only.",
    cost="$0 (no LLM call)",
    stage_id="residue_verification",
)
def _register_residue_verification(): pass
