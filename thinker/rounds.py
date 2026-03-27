"""Round execution for the Brain deliberation engine.

V8 spec Section 4:
- R1: just the brief (4 models, parallel)
- R2: brief + all R1 views + evidence + unaddressed arguments (3 models)
- R3: brief + R2 views + evidence + unaddressed arguments (2 models)
- R4: brief + R3 views + evidence + delta report + unaddressed arguments (2 models)

Topology: 4 -> 3 -> 2 -> 2
"""
from __future__ import annotations

import asyncio

from thinker.config import ROUND_TOPOLOGY
from thinker.types import ModelResponse, RoundResult


def build_round_prompt(
    round_num: int,
    brief: str,
    prior_views: dict[str, str],
    evidence_text: str,
    unaddressed_arguments: str,
) -> str:
    """Build the prompt for a given round.

    R1: just the brief.
    R2+: brief + prior views + evidence + unaddressed arguments.
    """
    parts = []

    parts.append("You are participating in a multi-model deliberation. "
                 "Analyze the following brief independently and thoroughly.\n")
    parts.append(f"## Brief\n\n{brief}\n")

    if round_num >= 2 and prior_views:
        parts.append("## Prior Round Views\n")
        parts.append("Other models provided these analyses in the previous round. "
                     "Consider their arguments but form your own independent judgment.\n")
        for model, view in prior_views.items():
            parts.append(f"### {model}\n{view}\n")

    if round_num >= 2 and evidence_text:
        parts.append(f"## Evidence\n\n{evidence_text}\n")

    if round_num >= 2 and unaddressed_arguments:
        parts.append("## Unaddressed Arguments From Prior Rounds\n")
        parts.append("The following arguments were raised but NOT substantively engaged with. "
                     "You MUST engage with each one — agree, rebut, or refine.\n")
        parts.append(f"{unaddressed_arguments}\n")

    parts.append("\n## Your Analysis\n")
    parts.append("Provide your independent assessment. Structure your response as:\n"
                 "1. Key findings\n"
                 "2. Your position (with confidence: HIGH/MEDIUM/LOW)\n"
                 "3. Key arguments supporting your position\n"
                 "4. Risks or uncertainties\n")

    return "\n".join(parts)


async def execute_round(
    client,
    round_num: int,
    brief: str,
    prior_views: dict[str, str] | None = None,
    evidence_text: str = "",
    unaddressed_arguments: str = "",
) -> RoundResult:
    """Execute a single deliberation round.

    Calls all models for this round in parallel. Returns a RoundResult
    with successful responses and a list of failed models.
    """
    models = ROUND_TOPOLOGY[round_num]
    prompt = build_round_prompt(
        round_num=round_num,
        brief=brief,
        prior_views=prior_views or {},
        evidence_text=evidence_text,
        unaddressed_arguments=unaddressed_arguments,
    )

    # Call all models in parallel
    tasks = {model: client.call(model, prompt) for model in models}
    responses: dict[str, ModelResponse] = {}
    results = await asyncio.gather(*tasks.values(), return_exceptions=True)

    failed = []
    for model, result in zip(tasks.keys(), results):
        if isinstance(result, Exception):
            responses[model] = ModelResponse(
                model=model, ok=False, text="", elapsed_s=0.0, error=str(result),
            )
            failed.append(model)
        elif not result.ok:
            responses[model] = result
            failed.append(model)
        else:
            responses[model] = result

    return RoundResult(round_num=round_num, responses=responses, failed=failed)
