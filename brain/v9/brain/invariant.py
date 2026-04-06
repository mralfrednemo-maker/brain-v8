"""Invariant Validator — structural integrity checks before proof finalization.

V8-F6 (Spec Section 4): Runs after Gate 2. Checks positions exist for every
round, all rounds have responses, evidence IDs are sequential, no orphaned
BLK/CTR references. Returns violations with severity (WARN or ERROR).
"""
from __future__ import annotations

from brain.evidence import EvidenceLedger
from brain.pipeline import pipeline_stage
from brain.tools.blocker import BlockerLedger
from brain.types import Position


def validate_invariants(
    positions_by_round: dict[int, dict[str, Position]],
    round_responded: dict[int, list[str]],
    evidence: EvidenceLedger,
    blocker_ledger: BlockerLedger,
    rounds_completed: int,
) -> list[dict]:
    """Run all invariant checks. Returns list of violation dicts.

    Each violation: {"id": str, "severity": "WARN"|"ERROR", "detail": str}
    """
    violations: list[dict] = []

    # 1. Positions extracted for every completed round
    for rnd in range(1, rounds_completed + 1):
        if rnd not in positions_by_round or not positions_by_round[rnd]:
            violations.append({
                "id": "INV-POS-MISSING",
                "severity": "ERROR",
                "detail": f"No positions extracted for round {rnd}",
            })

    # 2. All rounds have at least one response
    for rnd in range(1, rounds_completed + 1):
        responded = round_responded.get(rnd, [])
        if not responded:
            violations.append({
                "id": "INV-ROUND-EMPTY",
                "severity": "ERROR",
                "detail": f"Round {rnd} has no model responses",
            })

    # 3. Evidence IDs are sequential (E001, E002, ...)
    if evidence.items:
        for i, item in enumerate(evidence.items):
            expected_id = f"E{i + 1:03d}"
            if item.evidence_id != expected_id:
                violations.append({
                    "id": "INV-EVIDENCE-SEQ",
                    "severity": "WARN",
                    "detail": f"Evidence ID gap: expected {expected_id}, got {item.evidence_id}",
                })
                break  # One violation is enough to flag the issue

    # 4. No orphaned blocker references (detected_round within completed rounds)
    for b in blocker_ledger.blockers:
        if b.detected_round > rounds_completed:
            violations.append({
                "id": "INV-BLK-ORPHAN",
                "severity": "WARN",
                "detail": (
                    f"Blocker {b.blocker_id} references round {b.detected_round} "
                    f"but only {rounds_completed} rounds completed"
                ),
            })

    # 5. No orphaned contradiction evidence references
    evidence_ids = {item.evidence_id for item in evidence.items}
    for ctr in evidence.contradictions:
        for eid in ctr.evidence_ids:
            if eid not in evidence_ids:
                violations.append({
                    "id": "INV-CTR-ORPHAN",
                    "severity": "WARN",
                    "detail": (
                        f"Contradiction {ctr.ctr_id} references "
                        f"{eid} which is not in the evidence ledger"
                    ),
                })

    return violations


@pipeline_stage(
    name="Invariant Validator",
    description="Structural integrity checks after Gate 2. Verifies positions exist for every round, all rounds have responses, evidence IDs are sequential, no orphaned blocker or contradiction references. Returns violations with WARN/ERROR severity.",
    stage_type="deterministic",
    order=8,
    provider="deterministic (no LLM)",
    inputs=["positions_by_round", "round_responded", "evidence", "blocker_ledger", "rounds_completed"],
    outputs=["violations (list[dict]) — each with id, severity, detail"],
    logic="""1. For each round 1..N: positions extracted? If not → INV-POS-MISSING (ERROR)
2. For each round 1..N: at least one response? If not → INV-ROUND-EMPTY (ERROR)
3. Evidence IDs sequential (E001, E002, ...)? If gap → INV-EVIDENCE-SEQ (WARN)
4. Blocker detected_round <= rounds_completed? If not → INV-BLK-ORPHAN (WARN)
5. Contradiction evidence_ids all exist in ledger? If not → INV-CTR-ORPHAN (WARN)""",
    failure_mode="Cannot fail — deterministic computation.",
    cost="$0 (no LLM call)",
    stage_id="invariant_validator",
)
def _register_invariant_validator(): pass
