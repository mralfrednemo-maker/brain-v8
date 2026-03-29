"""Invariant Validator — structural integrity checks before proof finalization.

V8-F6 (Spec Section 4): Runs after Gate 2. Checks positions exist for every
round, all rounds have responses, evidence IDs are sequential, no orphaned
BLK/CTR references. Returns violations with severity (WARN or ERROR).
"""
from __future__ import annotations

from thinker.evidence import EvidenceLedger
from thinker.tools.blocker import BlockerLedger
from thinker.types import Position


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
                        f"Contradiction {ctr.contradiction_id} references "
                        f"{eid} which is not in the evidence ledger"
                    ),
                })

    return violations
