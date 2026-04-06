"""Argument Tracker — the core V8 innovation.

V8 spec Section 4, Argument Tracker:
After each round, one Sonnet call extracts all distinct arguments. Another
Sonnet call compares them with the next round's outputs to identify which
arguments were addressed, mentioned in passing, or ignored. Unaddressed
arguments are explicitly re-injected into the next round's prompt.

This replaces the Minority Archive, Acknowledgment Scanner, and all
keyword-matching machinery from V7.
"""
from __future__ import annotations

import re

from brain.pipeline import pipeline_stage
from brain.types import Argument, ArgumentStatus, BrainError


EXTRACT_PROMPT = """Read the following model outputs from round {round_num} of a multi-model deliberation.
Extract every distinct argument made by any model. An argument is a specific claim,
reasoning step, evidence interpretation, or position.

Model outputs:
{outputs}

List each argument as:
ARG-N: [model_name] argument text

Be exhaustive. Include ALL arguments, even minor ones. Do not merge arguments
from different models — track each separately."""

COMPARE_PROMPT = """Here are the arguments from round {prev_round}:
{arguments}

Here are the NEW arguments extracted from round {curr_round}:
{new_arguments}

Here are the model outputs from round {curr_round}:
{outputs}

For each argument from round {prev_round}, classify it as:
- ADDRESSED: The argument was directly engaged with (agreed, rebutted, or refined with reasoning)
- MENTIONED: The argument was referenced but not substantively engaged with
- IGNORED: The argument does not appear in any model's output at all

If ADDRESSED by refinement or supersession, also indicate which round {curr_round} argument replaces it.

Be strict. "Mentioned" means the model acknowledged the point but didn't reason about it.
"Addressed" requires genuine engagement — agreement with new reasoning, or a specific rebuttal.

Respond as:
ARG-N: ADDRESSED [superseded_by R{curr_round}-ARG-M] | ADDRESSED | MENTIONED | IGNORED

Only include [superseded_by ...] when a specific new argument clearly replaces or refines the old one."""


def parse_arguments(text: str, round_num: int) -> list[Argument]:
    """Parse extracted arguments from Sonnet's response.

    Handles multiple formats Sonnet may use:
      ARG-1: [r1] argument text
      ARG-1: r1 - argument text
      ARG-1: **r1** argument text
    """
    args = []
    for line in text.strip().split("\n"):
        line = line.strip()
        # Strip markdown bold/italic markers and leading bullet/dash
        line = re.sub(r"^\s*[-*•]\s*", "", line)
        line = re.sub(r"\*{1,2}(ARG-\d+.*?)\*{1,2}", r"\1", line)
        line = line.strip()
        # Try bracket format first: ARG-1: [model] text
        match = re.match(r"(ARG-\d+):\s+\[(\w+)\]\s+(.+)", line)
        if not match:
            # Try dash format: ARG-1: model - text
            match = re.match(r"(ARG-\d+):\s+[*]*(\w+)[*]*\s*[-–—]\s*(.+)", line)
        if not match:
            # Try bare format: ARG-1: model text (model is first word)
            match = re.match(r"(ARG-\d+):\s+[*]*(\w+)[*]*\s+(.+)", line)
        if match:
            model = match.group(2).lower()
            # Skip non-model words
            if model in ("the", "this", "that", "both", "all", "note"):
                continue
            # Prefix ARG-ID with round number to prevent cross-round collisions
            # LLM outputs ARG-1..ARG-N each round; R1-ARG-1 != R3-ARG-1
            raw_id = match.group(1)
            unique_id = f"R{round_num}-{raw_id}"
            args.append(Argument(
                argument_id=unique_id,
                round_num=round_num,
                model=model,
                text=match.group(3).strip(),
            ))
    return args


def parse_comparison(text: str, prev_round: int = 0) -> dict[str, tuple[ArgumentStatus, str | None]]:
    """Parse argument comparison from Sonnet's response.

    Handles both prefixed (R1-ARG-1) and unprefixed (ARG-1) IDs.
    When unprefixed, adds the R{prev_round} prefix to match stored IDs.

    Returns dict mapping argument_id -> (status, superseded_by_id or None).
    """
    statuses: dict[str, tuple[ArgumentStatus, str | None]] = {}
    for line in text.strip().split("\n"):
        line = line.strip()
        # Extract optional [superseded_by R2-ARG-3] tag
        superseded_by = None
        sup_match = re.search(r"\[superseded_by\s+(R\d+-ARG-\d+)\]", line)
        if sup_match:
            superseded_by = sup_match.group(1)

        # Try prefixed format first: R1-ARG-1: ADDRESSED [superseded_by ...]
        match = re.match(r"(R\d+-ARG-\d+):\s+(ADDRESSED|MENTIONED|IGNORED)", line)
        if match:
            statuses[match.group(1)] = (ArgumentStatus[match.group(2)], superseded_by)
            continue
        # Unprefixed format: ARG-1: ADDRESSED — add round prefix
        match = re.match(r"(ARG-\d+):\s+(ADDRESSED|MENTIONED|IGNORED)", line)
        if match:
            arg_id = f"R{prev_round}-{match.group(1)}" if prev_round else match.group(1)
            statuses[arg_id] = (ArgumentStatus[match.group(2)], superseded_by)
    return statuses


class ArgumentTracker:
    """Tracks arguments across rounds and re-injects unaddressed ones."""

    def __init__(self, llm_client):
        self._llm = llm_client
        self.arguments_by_round: dict[int, list[Argument]] = {}
        self.all_unaddressed: list[Argument] = []  # Cumulative across all rounds
        self.last_raw_response: str = ""  # For debug logging
        self._broken_supersession_links: list[dict] = []  # DOD §11.3 violations

    def assign_dimensions(self, arguments: list[Argument], dimension_names: dict[str, str]) -> None:
        """Post-hoc assignment of dimension_id to arguments by keyword matching.

        dimension_names: {dimension_id: name} e.g. {"DIM-1": "Technical Severity"}
        """
        for arg in arguments:
            if arg.dimension_id:
                continue  # Already assigned
            text_lower = arg.text.lower()
            best_match = ""
            best_score = 0
            for dim_id, dim_name in dimension_names.items():
                # Count keyword hits from dimension name
                keywords = [w.lower() for w in dim_name.split() if len(w) >= 3]
                score = sum(1 for kw in keywords if kw in text_lower)
                if score > best_score:
                    best_score = score
                    best_match = dim_id
            if best_match and best_score > 0:
                arg.dimension_id = best_match

    async def extract_arguments(
        self, round_num: int, model_outputs: dict[str, str],
    ) -> list[Argument]:
        from brain.types import BrainError
        combined = "\n\n".join(f"### {m}\n{t}" for m, t in model_outputs.items())
        resp = await self._llm.call(
            "sonnet",
            EXTRACT_PROMPT.format(round_num=round_num, outputs=combined),
        )
        if not resp.ok:
            raise BrainError(f"track{round_num}", f"Argument extraction failed: {resp.error}",
                             detail="Sonnet could not extract arguments from round outputs.")
        self.last_raw_response = resp.text
        args = parse_arguments(resp.text, round_num)
        if not args:
            raise BrainError(f"track{round_num}", "Argument extraction returned 0 arguments",
                             detail=f"Raw response: {resp.text[:300]}")
        self.arguments_by_round[round_num] = args
        return args

    async def compare_with_round(
        self, prev_round: int, curr_outputs: dict[str, str],
    ) -> list[Argument]:
        from brain.types import BrainError
        prev_args = self.arguments_by_round.get(prev_round, [])
        if not prev_args:
            return []

        args_text = "\n".join(
            f"{a.argument_id}: [{a.model}] {a.text}" for a in prev_args
        )
        curr_round = prev_round + 1
        curr_args = self.arguments_by_round.get(curr_round, [])
        new_args_text = "\n".join(
            f"{a.argument_id}: [{a.model}] {a.text}" for a in curr_args
        ) if curr_args else "(not yet extracted)"
        combined = "\n\n".join(f"### {m}\n{t}" for m, t in curr_outputs.items())

        resp = await self._llm.call(
            "sonnet",
            COMPARE_PROMPT.format(
                prev_round=prev_round, arguments=args_text,
                curr_round=curr_round, new_arguments=new_args_text,
                outputs=combined,
            ),
        )
        if not resp.ok:
            raise BrainError(f"track{curr_round}",
                             f"Argument comparison failed: {resp.error}",
                             detail=f"Could not compare R{prev_round} args against R{curr_round} outputs.")

        from brain.types import ResolutionStatus
        statuses = parse_comparison(resp.text, prev_round=prev_round)
        # Build set of valid curr_round arg IDs for supersession validation
        curr_args_by_id = {a.argument_id: a for a in curr_args}
        valid_curr_ids = set(curr_args_by_id)
        unaddressed = []
        for arg in prev_args:
            result = statuses.get(arg.argument_id, (ArgumentStatus.IGNORED, None))
            status, superseded_by_id = result
            arg.status = status
            if status in (ArgumentStatus.IGNORED, ArgumentStatus.MENTIONED):
                arg.addressed_in_round = None
                arg.open = True
                unaddressed.append(arg)
            else:
                arg.addressed_in_round = curr_round
                # Set superseded_by if valid (DOD §11.3)
                if superseded_by_id:
                    if superseded_by_id in valid_curr_ids:
                        # Fully resolved: explicit lineage link
                        arg.resolution_status = ResolutionStatus.SUPERSEDED
                        arg.superseded_by = superseded_by_id
                        arg.open = False
                        curr_args_by_id[superseded_by_id].refines = arg.argument_id
                    else:
                        # DOD §11.3: broken link — log and keep open (not fatal: LLM may hallucinate IDs)
                        arg.resolution_status = ResolutionStatus.REFINED
                        arg.open = True  # DOD §11.2: no valid lineage = not resolved
                        self._broken_supersession_links.append({
                            "argument_id": arg.argument_id,
                            "claimed_superseded_by": superseded_by_id,
                            "reason": "target ID not found in current round arguments",
                        })
                else:
                    # DOD §11.2: "Restatement without explicit linkage is NOT resolution"
                    # ADDRESSED without supersession tag = engaged but not formally resolved
                    arg.resolution_status = ResolutionStatus.REFINED
                    arg.open = True

        # Accumulate: add newly unaddressed args, remove any that were addressed
        addressed_ids = {a.argument_id for a in prev_args if a.status == ArgumentStatus.ADDRESSED}
        existing_ids = {a.argument_id for a in self.all_unaddressed}
        self.all_unaddressed = [
            a for a in self.all_unaddressed if a.argument_id not in addressed_ids
        ] + [a for a in unaddressed if a.argument_id not in existing_ids]
        return unaddressed

    def format_reinjection(self, unaddressed: list[Argument]) -> str:
        if not unaddressed:
            return ""
        lines = []
        for arg in unaddressed:
            status_label = "IGNORED" if arg.status == ArgumentStatus.IGNORED else "only mentioned"
            lines.append(f"{arg.argument_id}: [{arg.model}] {arg.text} ({status_label} in previous round)")
        return (
            "The following arguments from prior rounds were NOT substantively addressed. "
            "You MUST engage with each one — agree with reasoning, rebut with evidence, or refine.\n\n"
            + "\n".join(lines)
        )


@pipeline_stage(
    name="Argument Tracker",
    description="Core V8 innovation. After each round, Sonnet extracts all distinct arguments. After R2+, compares them with current round to identify ADDRESSED/MENTIONED/IGNORED. Unaddressed arguments re-injected into next round's prompt. Arguments can't be silently dropped.",
    stage_type="track",
    order=3,
    provider="sonnet (2 calls: extract + compare)",
    inputs=["model_outputs (dict[model, text])"],
    outputs=["arguments (list[Argument])", "unaddressed (list)", "reinjection_text (str)"],
    prompt=EXTRACT_PROMPT,
    logic="""EXTRACT: Sonnet reads all outputs, extracts ARG-N: [model] text.
COMPARE (R2+): For each prior arg — ADDRESSED (engaged), MENTIONED (name-dropped), IGNORED (absent).
RE-INJECT: IGNORED + MENTIONED args added to next round with "You MUST engage".""",
    failure_mode="Extract fails: empty args. Compare fails: re-inject all (conservative).",
    cost="2 Sonnet calls per round ($0 on Max subscription)",
    stage_id="argument_tracker",
)
def _register_argument_tracker(): pass
