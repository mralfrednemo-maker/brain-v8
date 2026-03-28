"""Checkpoint system for step-by-step pipeline debugging.

Usage:
  # Run up to a specific stage, save state, exit:
  python -m thinker.brain --brief b1.md --stop-after gate1

  # Inspect the checkpoint:
  python -m thinker.checkpoint output/checkpoint.json

  # Resume from checkpoint:
  python -m thinker.brain --resume output/checkpoint.json --stop-after r1

  # Resume and run to completion:
  python -m thinker.brain --resume output/checkpoint.json

Stage IDs for --stop-after:
  gate1, r1, track1, search1, r2, track2, search2, r3, track3, synthesis, gate2
"""
from __future__ import annotations

import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class PipelineState:
    """Serializable pipeline state for checkpointing."""
    brief: str = ""
    rounds: int = 3
    run_id: str = ""
    current_stage: str = ""
    completed_stages: list[str] = field(default_factory=list)

    # Gate 1
    gate1_passed: bool = False
    gate1_reasoning: str = ""
    gate1_questions: list[str] = field(default_factory=list)

    # Round outputs
    round_texts: dict[str, dict[str, str]] = field(default_factory=dict)  # {round_num: {model: text}}
    round_responded: dict[str, list[str]] = field(default_factory=dict)
    round_failed: dict[str, list[str]] = field(default_factory=dict)

    # Arguments
    arguments_by_round: dict[str, list[dict]] = field(default_factory=dict)
    unaddressed_text: str = ""
    all_unaddressed: list[dict] = field(default_factory=dict)

    # Positions
    positions_by_round: dict[str, dict[str, dict]] = field(default_factory=dict)
    position_changes: list[dict] = field(default_factory=list)

    # Evidence
    evidence_items: list[dict] = field(default_factory=list)
    evidence_count: int = 0

    # Search
    search_queries: dict[str, list[str]] = field(default_factory=dict)
    search_results: dict[str, int] = field(default_factory=dict)

    # Classification
    agreement_ratio: float = 0.0
    outcome_class: str = ""

    # Synthesis
    report: str = ""
    report_json: dict = field(default_factory=dict)

    # Gate 2
    outcome: str = ""

    def save(self, path: Path):
        path.write_text(json.dumps(asdict(self), indent=2, default=str), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "PipelineState":
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# Valid stage IDs in pipeline order
STAGE_ORDER = [
    "gate1",
    "r1", "track1", "search1",
    "r2", "track2", "search2",
    "r3", "track3",
    "synthesis", "gate2",
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
