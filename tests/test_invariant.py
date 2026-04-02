"""Tests for the invariant validator."""
import pytest

from thinker.invariant import validate_invariants
from thinker.types import (
    Argument, ArgumentStatus, Blocker, BlockerKind, BlockerStatus,
    Confidence, Contradiction, EvidenceItem, Position,
)
from thinker.tools.blocker import BlockerLedger
from thinker.evidence import EvidenceLedger


def _make_positions(rounds: dict[int, dict[str, str]]) -> dict[int, dict[str, Position]]:
    """Helper: {round_num: {model: option}} -> position tracker format."""
    result = {}
    for rnd, models in rounds.items():
        result[rnd] = {
            m: Position(m, rnd, opt, confidence=Confidence.HIGH)
            for m, opt in models.items()
        }
    return result


class TestValidateInvariants:

    def test_clean_run_no_violations(self):
        positions = _make_positions({
            1: {"r1": "O3", "reasoner": "O3", "glm5": "O3", "kimi": "O3"},
            2: {"r1": "O3", "reasoner": "O3", "glm5": "O3"},
            3: {"r1": "O3", "reasoner": "O3"},
        })
        round_responded = {1: ["r1", "reasoner", "glm5", "kimi"],
                           2: ["r1", "reasoner", "glm5"],
                           3: ["r1", "reasoner"]}
        evidence = EvidenceLedger(max_items=10)
        evidence.add(EvidenceItem("E001", "t", "fact", "https://a.com", Confidence.HIGH))
        blocker_ledger = BlockerLedger()

        violations = validate_invariants(
            positions_by_round=positions,
            round_responded=round_responded,
            evidence=evidence,
            blocker_ledger=blocker_ledger,
            rounds_completed=3,
        )
        assert violations == []

    def test_missing_positions_for_round(self):
        positions = _make_positions({
            1: {"r1": "O3", "reasoner": "O3"},
            # Round 2 missing entirely
            3: {"r1": "O3", "reasoner": "O3"},
        })
        round_responded = {1: ["r1", "reasoner"], 2: ["r1", "reasoner"], 3: ["r1", "reasoner"]}

        violations = validate_invariants(
            positions_by_round=positions,
            round_responded=round_responded,
            evidence=EvidenceLedger(),
            blocker_ledger=BlockerLedger(),
            rounds_completed=3,
        )
        assert any(v["id"] == "INV-POS-MISSING" for v in violations)

    def test_round_without_responses(self):
        positions = _make_positions({1: {"r1": "O3"}})
        round_responded = {1: ["r1"], 2: []}  # Round 2 has no responses

        violations = validate_invariants(
            positions_by_round=positions,
            round_responded=round_responded,
            evidence=EvidenceLedger(),
            blocker_ledger=BlockerLedger(),
            rounds_completed=2,
        )
        assert any(v["id"] == "INV-ROUND-EMPTY" for v in violations)

    def test_non_sequential_evidence_ids(self):
        evidence = EvidenceLedger(max_items=10)
        e1 = EvidenceItem("E001", "t", "fact 1", "https://a.com", Confidence.HIGH)
        e3 = EvidenceItem("E003", "t different", "fact 3 different", "https://b.com", Confidence.HIGH)
        evidence.active_items = [e1, e3]  # Gap: E002 missing

        violations = validate_invariants(
            positions_by_round={1: {"r1": Position("r1", 1, "O3")}},
            round_responded={1: ["r1"]},
            evidence=evidence,
            blocker_ledger=BlockerLedger(),
            rounds_completed=1,
        )
        assert any(v["id"] == "INV-EVIDENCE-SEQ" for v in violations)

    def test_orphaned_blocker_references(self):
        blocker_ledger = BlockerLedger()
        # Blocker references round 5, but only 3 rounds completed
        blocker_ledger.add(
            kind=BlockerKind.EVIDENCE_GAP,
            source="test",
            detected_round=5,
            detail="orphaned",
        )

        violations = validate_invariants(
            positions_by_round={1: {"r1": Position("r1", 1, "O3")}},
            round_responded={1: ["r1"]},
            evidence=EvidenceLedger(),
            blocker_ledger=blocker_ledger,
            rounds_completed=3,
        )
        assert any(v["id"] == "INV-BLK-ORPHAN" for v in violations)

    def test_orphaned_contradiction_references(self):
        evidence = EvidenceLedger(max_items=10)
        e1 = EvidenceItem("E001", "t", "fact 1", "https://a.com", Confidence.HIGH)
        evidence.active_items = [e1]
        # Contradiction references E099 which doesn't exist
        evidence.contradictions = [
            Contradiction("CTR001", ["E001", "E099"], "t", "HIGH"),
        ]

        violations = validate_invariants(
            positions_by_round={1: {"r1": Position("r1", 1, "O3")}},
            round_responded={1: ["r1"]},
            evidence=evidence,
            blocker_ledger=BlockerLedger(),
            rounds_completed=1,
        )
        assert any(v["id"] == "INV-CTR-ORPHAN" for v in violations)

    def test_violation_has_severity(self):
        positions = _make_positions({})
        round_responded = {1: []}

        violations = validate_invariants(
            positions_by_round=positions,
            round_responded=round_responded,
            evidence=EvidenceLedger(),
            blocker_ledger=BlockerLedger(),
            rounds_completed=1,
        )
        for v in violations:
            assert v["severity"] in ("WARN", "ERROR")
            assert "detail" in v
