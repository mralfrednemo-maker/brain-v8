"""Tests for Synthesis Packet builder (DoD v3.0 Section 14)."""
import pytest

from thinker.types import (
    Argument, ArgumentStatus, Blocker, BlockerKind, BlockerStatus,
    Confidence, Contradiction, DecisiveClaim, EvidenceSupportStatus,
    FrameInfo, FrameSurvivalStatus, Position, PremiseFlag,
    PremiseFlagSeverity, PremiseFlagType, PremiseFlagRouting,
    ResolutionStatus, SemanticContradiction, ContradictionSeverity,
    ContradictionStatus, EvidenceItem,
)


def test_build_packet_basic():
    from thinker.synthesis_packet import build_synthesis_packet
    positions = {
        "r1": Position("r1", 4, "Option A", confidence=Confidence.HIGH),
        "reasoner": Position("reasoner", 4, "Option A", confidence=Confidence.HIGH),
    }
    packet = build_synthesis_packet(
        brief="Test brief",
        final_positions=positions,
        arguments=[],
        frames=[],
        blockers=[],
        decisive_claims=[],
        contradictions_numeric=[],
        contradictions_semantic=[],
        premise_flags=[],
        evidence_items=[],
    )
    assert "final_positions" in packet
    assert len(packet["final_positions"]) == 2
    assert packet["final_positions"][0]["model_id"] == "r1"
    assert packet["argument_count_total"] == 0


def test_packet_caps_arguments():
    from thinker.synthesis_packet import build_synthesis_packet
    args = [
        Argument(f"ARG-{i}", round_num=1, model="r1", text=f"arg {i}")
        for i in range(30)
    ]
    packet = build_synthesis_packet(
        brief="Test",
        final_positions={},
        arguments=args,
        frames=[],
        blockers=[],
        decisive_claims=[],
        contradictions_numeric=[],
        contradictions_semantic=[],
        premise_flags=[],
        evidence_items=[],
        max_arguments=20,
    )
    assert len(packet["argument_lifecycle"]) == 20
    assert packet["argument_count_total"] == 30


def test_packet_includes_open_blockers_only():
    from thinker.synthesis_packet import build_synthesis_packet
    blockers = [
        Blocker("BLK-1", BlockerKind.EVIDENCE_GAP, "test", 1, status=BlockerStatus.OPEN),
        Blocker("BLK-2", BlockerKind.CONTRADICTION, "test", 2, status=BlockerStatus.RESOLVED),
    ]
    packet = build_synthesis_packet(
        brief="Test",
        final_positions={},
        arguments=[],
        frames=[],
        blockers=blockers,
        decisive_claims=[],
        contradictions_numeric=[],
        contradictions_semantic=[],
        premise_flags=[],
        evidence_items=[],
    )
    assert packet["open_blocker_count"] == 1
    assert len(packet["blocker_summary"]) == 1


def test_packet_material_unrebutted_frames():
    from thinker.synthesis_packet import build_synthesis_packet
    frames = [
        FrameInfo("FRAME-1", "test", survival_status=FrameSurvivalStatus.ACTIVE),
        FrameInfo("FRAME-2", "test", survival_status=FrameSurvivalStatus.DROPPED),
        FrameInfo("FRAME-3", "test", survival_status=FrameSurvivalStatus.CONTESTED),
    ]
    packet = build_synthesis_packet(
        brief="Test",
        final_positions={},
        arguments=[],
        frames=frames,
        blockers=[],
        decisive_claims=[],
        contradictions_numeric=[],
        contradictions_semantic=[],
        premise_flags=[],
        evidence_items=[],
    )
    assert packet["material_unrebutted_frames"] == 2


def test_format_packet_for_prompt():
    from thinker.synthesis_packet import build_synthesis_packet, format_synthesis_packet_for_prompt
    packet = build_synthesis_packet(
        brief="Test brief",
        final_positions={
            "r1": Position("r1", 4, "Option A", confidence=Confidence.HIGH),
        },
        arguments=[],
        frames=[],
        blockers=[],
        decisive_claims=[],
        contradictions_numeric=[],
        contradictions_semantic=[],
        premise_flags=[],
        evidence_items=[],
    )
    text = format_synthesis_packet_for_prompt(packet)
    assert "Final Positions" in text
    assert "Option A" in text
    assert "r1" in text
    assert "Disposition Requirements" in text
