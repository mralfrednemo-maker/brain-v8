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

from thinker.pipeline import pipeline_stage
from thinker.types import Argument, ArgumentStatus


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

Here are the model outputs from round {curr_round}:
{outputs}

For each argument, classify it as:
- ADDRESSED: The argument was directly engaged with (agreed, rebutted, or refined with reasoning)
- MENTIONED: The argument was referenced but not substantively engaged with
- IGNORED: The argument does not appear in any model's output at all

Be strict. "Mentioned" means the model acknowledged the point but didn't reason about it.
"Addressed" requires genuine engagement — agreement with new reasoning, or a specific rebuttal.

Respond as:
ARG-N: ADDRESSED | MENTIONED | IGNORED"""


def parse_arguments(text: str, round_num: int) -> list[Argument]:
    """Parse extracted arguments from Sonnet's response."""
    args = []
    for line in text.strip().split("\n"):
        line = line.strip()
        match = re.match(r"(ARG-\d+):\s+\[(\w+)\]\s+(.+)", line)
        if match:
            args.append(Argument(
                argument_id=match.group(1),
                round_num=round_num,
                model=match.group(2),
                text=match.group(3).strip(),
            ))
    return args


def parse_comparison(text: str) -> dict[str, ArgumentStatus]:
    """Parse argument comparison from Sonnet's response."""
    statuses: dict[str, ArgumentStatus] = {}
    for line in text.strip().split("\n"):
        line = line.strip()
        match = re.match(r"(ARG-\d+):\s+(ADDRESSED|MENTIONED|IGNORED)", line)
        if match:
            statuses[match.group(1)] = ArgumentStatus[match.group(2)]
    return statuses


class ArgumentTracker:
    """Tracks arguments across rounds and re-injects unaddressed ones."""

    def __init__(self, llm_client):
        self._llm = llm_client
        self.arguments_by_round: dict[int, list[Argument]] = {}
        self.all_unaddressed: list[Argument] = []

    async def extract_arguments(
        self, round_num: int, model_outputs: dict[str, str],
    ) -> list[Argument]:
        combined = "\n\n".join(f"### {m}\n{t}" for m, t in model_outputs.items())
        resp = await self._llm.call(
            "sonnet",
            EXTRACT_PROMPT.format(round_num=round_num, outputs=combined),
        )
        if not resp.ok:
            return []
        args = parse_arguments(resp.text, round_num)
        self.arguments_by_round[round_num] = args
        return args

    async def compare_with_round(
        self, prev_round: int, curr_outputs: dict[str, str],
    ) -> list[Argument]:
        prev_args = self.arguments_by_round.get(prev_round, [])
        if not prev_args:
            return []

        args_text = "\n".join(
            f"{a.argument_id}: [{a.model}] {a.text}" for a in prev_args
        )
        combined = "\n\n".join(f"### {m}\n{t}" for m, t in curr_outputs.items())
        curr_round = prev_round + 1

        resp = await self._llm.call(
            "sonnet",
            COMPARE_PROMPT.format(
                prev_round=prev_round, arguments=args_text,
                curr_round=curr_round, outputs=combined,
            ),
        )
        if not resp.ok:
            return prev_args

        statuses = parse_comparison(resp.text)
        unaddressed = []
        for arg in prev_args:
            status = statuses.get(arg.argument_id, ArgumentStatus.IGNORED)
            arg.status = status
            if status in (ArgumentStatus.IGNORED, ArgumentStatus.MENTIONED):
                arg.addressed_in_round = None
                unaddressed.append(arg)
            else:
                arg.addressed_in_round = curr_round

        self.all_unaddressed = unaddressed
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
