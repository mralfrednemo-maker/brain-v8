"""Checkpoint system for step-by-step pipeline debugging.

Usage:
  # Run up to a specific stage, save state, exit:
  python -m thinker.brain --brief b1.md --stop-after preflight

  # Inspect the checkpoint:
  python -m thinker.checkpoint output/checkpoint.json

  # Resume from checkpoint:
  python -m thinker.brain --resume output/checkpoint.json --stop-after r1

  # Resume and run to completion:
  python -m thinker.brain --resume output/checkpoint.json

Stage IDs for --stop-after (V9):
  preflight, dimensions, r1, track1, perspective_cards, framing_pass,
  ungrounded_r1, search1, r2, track2, frame_survival_r2, ungrounded_r2,
  search2, r3, track3, frame_survival_r3, r4, track4,
  semantic_contradiction, decisive_claims, synthesis_packet, synthesis, stability, gate2
"""
from __future__ import annotations

import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

CHECKPOINT_VERSION = "3.0"


@dataclass
class PipelineState:
    """Serializable pipeline state for checkpointing."""
    checkpoint_version: str = CHECKPOINT_VERSION
    brief: str = ""
    rounds: int = 4
    run_id: str = ""
    current_stage: str = ""
    completed_stages: list[str] = field(default_factory=list)

    # Gate 1 (legacy, kept for backward compat)
    gate1_passed: bool = False
    gate1_reasoning: str = ""
    gate1_questions: list[str] = field(default_factory=list)
    gate1_search_recommended: bool = True
    gate1_search_reasoning: str = ""

    # V9: PreflightAssessment
    preflight: dict = field(default_factory=dict)
    modality: str = "DECIDE"

    # V9: Dimensions
    dimensions: dict = field(default_factory=dict)

    # V9: Perspective Cards
    perspective_cards: list[dict] = field(default_factory=list)

    # V9: Divergence
    divergence: dict = field(default_factory=dict)
    adversarial_model: str = ""

    # Round outputs
    round_texts: dict[str, dict[str, str]] = field(default_factory=dict)  # {round_num: {model: text}}
    round_responded: dict[str, list[str]] = field(default_factory=dict)
    round_failed: dict[str, list[str]] = field(default_factory=dict)

    # Arguments
    arguments_by_round: dict[str, list[dict]] = field(default_factory=dict)
    unaddressed_text: str = ""
    all_unaddressed: list[dict] = field(default_factory=list)

    # Positions
    positions_by_round: dict[str, dict[str, dict]] = field(default_factory=dict)
    position_changes: list[dict] = field(default_factory=list)

    # Evidence
    evidence_items: list[dict] = field(default_factory=list)
    evidence_count: int = 0

    # V9: Search log
    search_log: list[dict] = field(default_factory=list)

    # Search
    search_queries: dict[str, list[str]] = field(default_factory=dict)
    search_results: dict[str, int] = field(default_factory=dict)

    # V9: Ungrounded stats tracking (DOD §9.2)
    ungrounded_flagged_claims: list[dict] = field(default_factory=list)
    ungrounded_r1_executed: bool = False
    ungrounded_r2_executed: bool = False

    # Classification
    agreement_ratio: float = 0.0
    outcome_class: str = ""

    # Synthesis
    report: str = ""
    report_json: dict = field(default_factory=dict)

    # V9: Stability
    stability: dict = field(default_factory=dict)

    # Gate 2
    outcome: str = ""

    # V3.1 additions
    retroactive_escalation_consumed: bool = False
    retroactive_premise_result: dict = field(default_factory=dict)
    anti_groupthink_search: dict = field(default_factory=dict)
    breadth_recovery: dict = field(default_factory=dict)
    warnings: list[dict] = field(default_factory=list)
    original_brief: str = ""
    reformulated_brief: str = ""
    reformulation_reason: str = ""

    def save(self, path: Path):
        path.write_text(json.dumps(asdict(self), indent=2, default=str), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "PipelineState":
        data = json.loads(path.read_text(encoding="utf-8"))
        saved_version = data.get("checkpoint_version", "0.0")
        if saved_version != CHECKPOINT_VERSION:
            raise ValueError(
                f"Checkpoint version mismatch: file has {saved_version}, "
                f"code expects {CHECKPOINT_VERSION}. "
                f"Delete the checkpoint and re-run from scratch."
            )
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# Valid stage IDs in pipeline order (V10)
STAGE_ORDER = [
    "preflight", "dimensions",
    "r1", "track1", "retroactive_premise_scan", "perspective_cards", "framing_pass",
    "anti_groupthink_search", "ungrounded_r1", "search1",
    "r2", "track2", "frame_survival_r2", "breadth_recovery_eval",
    "ungrounded_r2", "search2",
    "r3", "track3", "frame_survival_r3",
    "r4", "track4",
    "semantic_contradiction", "decisive_claims", "synthesis_packet",
    "synthesis", "stability", "residue_verification", "gate2",
]


def should_stop(current_stage: str, stop_after: Optional[str]) -> bool:
    """Check if we should stop after the current stage."""
    if not stop_after:
        return False
    if current_stage == stop_after:
        return True
    return False


def print_checkpoint(path: str):
    """Pretty-print a checkpoint file for inspection."""
    state = PipelineState.load(Path(path))
    print(f"\n{'='*60}")
    print(f"  CHECKPOINT: {path}")
    print(f"{'='*60}")
    print(f"  Run ID:     {state.run_id}")
    print(f"  Brief:      {len(state.brief)} chars")
    print(f"  Stage:      {state.current_stage}")
    print(f"  Completed:  {' → '.join(state.completed_stages)}")
    print()

    if "gate1" in state.completed_stages:
        print(f"  Gate 1:     {'PASS' if state.gate1_passed else 'NEED_MORE'}")
        print(f"  Reasoning:  {state.gate1_reasoning[:150]}...")
        print()

    for rnd in ["1", "2", "3"]:
        if rnd in state.round_responded:
            responded = state.round_responded[rnd]
            failed = state.round_failed.get(rnd, [])
            print(f"  R{rnd}: responded={responded}, failed={failed}")
            # Show positions if available
            if rnd in state.positions_by_round:
                for m, p in state.positions_by_round[rnd].items():
                    print(f"    {m}: {p.get('option', '?')} [{p.get('confidence', '?')}]")
            # Show args
            if rnd in state.arguments_by_round:
                n = len(state.arguments_by_round[rnd])
                print(f"    Arguments: {n}")
            print()

    if state.search_results:
        for phase, count in state.search_results.items():
            print(f"  Search {phase}: {state.search_queries.get(phase, ['?'])} → {count} evidence")
        print()

    if state.outcome_class:
        print(f"  Agreement:  {state.agreement_ratio:.2f}")
        print(f"  Class:      {state.outcome_class}")
        print(f"  Outcome:    {state.outcome}")
        print()

    if state.report:
        print(f"  Report:     {len(state.report)} chars")
    print(f"{'='*60}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print_checkpoint(sys.argv[1])
    else:
        print("Usage: python -m thinker.checkpoint <checkpoint.json>")
        print(f"\nValid stage IDs for --stop-after: {', '.join(STAGE_ORDER)}")
