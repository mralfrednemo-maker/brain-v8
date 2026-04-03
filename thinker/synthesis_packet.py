"""Synthesis Packet — controller-curated state bundle (DoD v3.0 Section 14).

Builds the curated packet that synthesis receives instead of raw R4 views.
Includes: final positions, argument lifecycle, frame summary, blocker summary,
decisive claim bindings, contradiction summary, premise flag summary.
"""
from __future__ import annotations

from typing import Optional

from thinker.types import (
    Argument, Blocker, BlockerStatus, Contradiction, CriticalAssumption,
    DecisiveClaim, DivergenceResult, EvidenceItem, FrameInfo,
    FrameSurvivalStatus, Position, PremiseFlag, SemanticContradiction,
)


def build_synthesis_packet(
    brief: str,
    final_positions: dict[str, Position],
    arguments: list[Argument],
    frames: list[FrameInfo],
    blockers: list[Blocker],
    decisive_claims: list[DecisiveClaim],
    contradictions_numeric: list[Contradiction],
    contradictions_semantic: list[SemanticContradiction],
    premise_flags: list[PremiseFlag],
    evidence_items: list[EvidenceItem],
    max_arguments: int = 20,
) -> dict:
    """Build the curated synthesis packet.

    Returns a dict suitable for injection into the synthesis prompt.
    """
    # Argument lifecycle — cap at max_arguments, prioritize open/material
    sorted_args = sorted(arguments, key=lambda a: (not a.open, a.round_num))
    capped_args = sorted_args[:max_arguments]
    arg_entries = []
    for a in capped_args:
        arg_entries.append({
            "argument_id": a.argument_id,
            "round": a.round_num,
            "model": a.model,
            "text": a.text[:200],
            "status": a.status.value,
            "resolution_status": a.resolution_status.value,
            "open": a.open,
            "dimension_id": a.dimension_id,
        })

    # Frame summary
    frame_entries = []
    for f in frames:
        frame_entries.append({
            "frame_id": f.frame_id,
            "text": f.text[:150],
            "survival_status": f.survival_status.value,
            "material": f.material_to_outcome,
            "disposition": f.synthesis_disposition_status,
        })

    # Blocker summary
    open_blockers = [b for b in blockers if b.status == BlockerStatus.OPEN]
    blocker_entries = []
    for b in open_blockers:
        blocker_entries.append({
            "blocker_id": b.blocker_id,
            "kind": b.kind.value,
            "detail": b.detail[:150],
        })

    # Decisive claim bindings
    claim_entries = [c.to_dict() for c in decisive_claims] if decisive_claims else []

    # Contradiction summary
    ctr_entries = []
    for c in contradictions_numeric:
        if c.status != "RESOLVED":
            ctr_entries.append({
                "id": c.contradiction_id,
                "mode": "NUMERIC",
                "topic": c.topic,
                "severity": c.severity,
            })
    for c in contradictions_semantic:
        if c.status.value != "RESOLVED":
            ctr_entries.append({
                "id": c.ctr_id,
                "mode": "SEMANTIC",
                "severity": c.severity.value,
                "justification": c.justification[:150],
            })

    # Premise flags
    flag_entries = []
    for f in premise_flags:
        if not f.resolved:
            flag_entries.append({
                "flag_id": f.flag_id,
                "type": f.flag_type.value,
                "severity": f.severity.value,
                "summary": f.summary[:150],
            })

    # DOD §14: packet_complete — all required sections present
    packet_complete = (
        len(final_positions) > 0
        and len(arguments) > 0
        and evidence_items is not None
    )

    return {
        "packet_complete": packet_complete,
        "brief_excerpt": brief[:500],
        "final_positions": {
            m: {"option": p.primary_option, "confidence": p.confidence.value}
            for m, p in final_positions.items()
        },
        "argument_lifecycle": arg_entries,
        "argument_count_total": len(arguments),
        "argument_count_open": sum(1 for a in arguments if a.open),
        "frame_summary": frame_entries,
        "material_unrebutted_frames": sum(
            1 for f in frames
            if f.material_to_outcome
            and f.survival_status in (FrameSurvivalStatus.ACTIVE, FrameSurvivalStatus.CONTESTED)
        ),
        "blocker_summary": blocker_entries,
        "open_blocker_count": len(open_blockers),
        "decisive_claims": claim_entries,
        "contradiction_summary": ctr_entries,
        "premise_flag_summary": flag_entries,
        "evidence_count": len(evidence_items),
    }


def format_synthesis_packet_for_prompt(packet: dict) -> str:
    """Format the synthesis packet as text for the synthesis prompt."""
    lines = ["## Curated State Bundle (AUTHORITATIVE — use this, not raw round views)\n"]

    # Positions
    lines.append("### Final Positions")
    for model, pos in packet.get("final_positions", {}).items():
        lines.append(f"- **{model}**: {pos['option']} [{pos['confidence']}]")

    # Arguments
    lines.append(f"\n### Argument Lifecycle ({packet.get('argument_count_open', 0)} open / {packet.get('argument_count_total', 0)} total)")
    for a in packet.get("argument_lifecycle", [])[:10]:
        status = "OPEN" if a["open"] else a["resolution_status"]
        lines.append(f"- [{a['argument_id']}] {a['text'][:100]}... ({status})")

    # Frames
    frames = packet.get("frame_summary", [])
    if frames:
        lines.append(f"\n### Alternative Frames ({len(frames)})")
        for f in frames:
            lines.append(f"- [{f['frame_id']}] {f['text'][:80]}... ({f['survival_status']})")

    # Blockers
    blockers = packet.get("blocker_summary", [])
    if blockers:
        lines.append(f"\n### Open Blockers ({len(blockers)})")
        for b in blockers:
            lines.append(f"- [{b['blocker_id']}] {b['kind']}: {b['detail'][:80]}...")

    # Claims
    claims = packet.get("decisive_claims", [])
    if claims:
        lines.append(f"\n### Decisive Claims ({len(claims)})")
        for c in claims:
            status = c.get("evidence_support_status", "UNSUPPORTED")
            lines.append(f"- [{c['claim_id']}] {c['text'][:80]}... ({status})")

    # Contradictions
    ctrs = packet.get("contradiction_summary", [])
    if ctrs:
        lines.append(f"\n### Unresolved Contradictions ({len(ctrs)})")
        for c in ctrs:
            lines.append(f"- [{c['id']}] {c['mode']} | {c['severity']}")

    # Premise flags
    flags = packet.get("premise_flag_summary", [])
    if flags:
        lines.append(f"\n### Unresolved Premise Flags ({len(flags)})")
        for f in flags:
            lines.append(f"- [{f['flag_id']}] {f['type']}: {f['summary'][:80]}...")

    lines.append("\n### Disposition Requirements")
    lines.append("You MUST provide a structured disposition for EVERY:")
    lines.append("- Open blocker")
    lines.append("- Active/contested frame")
    lines.append("- Decisive claim")
    lines.append("- Unresolved contradiction")
    lines.append("- Orphaned high-authority evidence not cited in your report")

    return "\n".join(lines)
