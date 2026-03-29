"""Post-synthesis residue verification.

V8-F1 (DoD D7): After synthesis, scan the report text to verify it
mentions all structural findings — blocker IDs, contradiction IDs,
and unaddressed argument IDs. This is a narrative completeness check,
not truth verification.
"""
from __future__ import annotations

from thinker.pipeline import pipeline_stage
from thinker.types import Argument, Blocker, Contradiction


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
