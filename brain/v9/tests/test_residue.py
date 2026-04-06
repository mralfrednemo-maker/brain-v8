"""Tests for post-synthesis residue verification."""
import pytest

from brain.residue import check_synthesis_residue
from brain.types import (
    Argument, ArgumentStatus, Blocker, BlockerKind, BlockerStatus,
    Contradiction,
)


class TestCheckSynthesisResidue:

    def test_all_mentioned_returns_empty(self):
        report = "BLK001 was identified. CTR001 between E001 and E002. R1-ARG-1 was addressed."
        blockers = [Blocker("BLK001", BlockerKind.EVIDENCE_GAP, "test", 1)]
        contradictions = [Contradiction("CTR001", ["E001", "E002"], "t", "HIGH")]
        arguments = [Argument("R1-ARG-1", 1, "r1", "some point", ArgumentStatus.IGNORED)]

        omissions = check_synthesis_residue(report, blockers, contradictions, arguments)
        assert omissions == []

    def test_missing_blocker_id(self):
        report = "The deliberation found consensus."
        blockers = [Blocker("BLK001", BlockerKind.EVIDENCE_GAP, "test", 1)]

        omissions = check_synthesis_residue(report, blockers, [], [])
        assert any(o["type"] == "blocker" and o["id"] == "BLK001" for o in omissions)

    def test_missing_contradiction_id(self):
        report = "Models agreed on the conclusion."
        contradictions = [Contradiction("CTR001", ["E001", "E002"], "t", "HIGH")]

        omissions = check_synthesis_residue(report, [], contradictions, [])
        assert any(o["type"] == "contradiction" and o["id"] == "CTR001" for o in omissions)

    def test_missing_unaddressed_argument(self):
        report = "The report covers all points."
        args = [Argument("R1-ARG-1", 1, "r1", "important claim", ArgumentStatus.IGNORED)]

        omissions = check_synthesis_residue(report, [], [], args)
        assert any(o["type"] == "argument" and o["id"] == "R1-ARG-1" for o in omissions)

    def test_threshold_violation_flagged(self):
        """If >30% of structural findings omitted, flag it."""
        report = "Short report with no references."
        blockers = [Blocker(f"BLK{i:03d}", BlockerKind.EVIDENCE_GAP, "t", 1) for i in range(1, 5)]
        contradictions = [Contradiction(f"CTR{i:03d}", ["E001"], "t", "HIGH") for i in range(1, 4)]
        args = [Argument(f"R1-ARG-{i}", 1, "r1", f"arg {i}", ArgumentStatus.IGNORED) for i in range(1, 4)]

        omissions = check_synthesis_residue(report, blockers, contradictions, args)
        # All 10 items omitted = 100% > 30% threshold
        assert any(o.get("threshold_violation") for o in omissions)

    def test_partial_coverage_no_threshold_violation(self):
        """If <=30% omitted, no threshold violation."""
        # 10 blockers, report mentions 8 of them → 20% omission < 30%
        report = "BLK001 BLK002 BLK003 BLK004 BLK005 BLK006 BLK007 BLK008"
        blockers = [Blocker(f"BLK{i:03d}", BlockerKind.EVIDENCE_GAP, "t", 1) for i in range(1, 11)]

        omissions = check_synthesis_residue(report, blockers, [], [])
        assert not any(o.get("threshold_violation") for o in omissions)

    def test_empty_inputs_no_omissions(self):
        omissions = check_synthesis_residue("any report text", [], [], [])
        assert omissions == []

    def test_omission_dict_structure(self):
        report = "nothing here"
        blockers = [Blocker("BLK001", BlockerKind.EVIDENCE_GAP, "test", 1)]
        omissions = check_synthesis_residue(report, blockers, [], [])
        assert len(omissions) == 1
        assert "type" in omissions[0]
        assert "id" in omissions[0]
