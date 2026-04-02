"""Round execution for the Brain deliberation engine.

Topology: 4 -> 3 -> 2 -> 2
- R1: brief only (4 models, parallel)
- R2: brief + R1 views + evidence + unaddressed arguments (3 models)
- R3: brief + R2 views + evidence + unaddressed arguments (2 models)

Search requests: R1 and R2 prompts include a section asking models to list
0-5 search queries as an appendix. R3 does not (final convergence round).
"""
from __future__ import annotations

import asyncio

from thinker.config import ROUND_TOPOLOGY
from thinker.pipeline import pipeline_stage
from thinker.types import ModelResponse, RoundResult

# Evidence framing — makes clear that web-verified evidence outranks model opinions
_EVIDENCE_HEADER = (
    "## Web-Verified Evidence (AUTHORITATIVE — outranks model opinions)\n\n"
    "The following facts were retrieved from web sources and verified. "
    "When a model's prior claim conflicts with evidence below, the evidence takes precedence. "
    "Cite evidence IDs (E001-E999) when referencing these facts.\n\n"
)

_SEARCH_REQUEST_SECTION = (
    "\n## Search Requests (optional, 0-5)\n"
    "After your analysis, you may list 0-5 specific questions you want fact-checked "
    "via web search before the next round. These will be searched and results injected "
    "into the next round's prompt. If you have no search requests, write NONE.\n\n"
    "Format:\n"
    "SEARCH_REQUESTS:\n"
    "1. [specific, searchable query]\n"
    "2. ...\n"
)


_ADVERSARIAL_PREAMBLE = (
    "## ADVERSARIAL ROLE (assigned to you)\n"
    "You are the designated adversarial voice. Your job is to:\n"
    "- Challenge the dominant framing\n"
    "- Attack hidden assumptions\n"
    "- Propose alternative interpretations\n"
    "- Be the devil's advocate\n"
    "Do NOT simply agree with the obvious position.\n\n"
)

_FRAME_ENGAGEMENT_SECTION = (
    "\n## Frame Engagement Requirements (MANDATORY for R2)\n"
    "You MUST:\n"
    "1. ADOPT at least one alternative frame and argue from its perspective\n"
    "2. REBUT at least one alternative frame with substantive counter-arguments\n"
    "3. GENERATE at least one NEW alternative frame not yet proposed\n\n"
    "For each, clearly label: ADOPT: [frame_id], REBUT: [frame_id], NEW_FRAME: [description]\n"
)


def build_round_prompt(
    round_num: int,
    brief: str,
    prior_views: dict[str, str],
    evidence_text: str,
    unaddressed_arguments: str,
    is_last_round: bool = False,
    adversarial_model: str = "",
    model_id: str = "",
    alt_frames_text: str = "",
    dimension_text: str = "",
    perspective_card_instructions: str = "",
) -> str:
    """Build the prompt for a given round.

    R1: brief + search request appendix.
    R2: brief + prior views + evidence + unaddressed args + search request appendix.
    R3: brief + prior views + evidence + unaddressed args (no search — final round).

    V9 extensions:
    - R1: adversarial preamble (if model_id == adversarial_model),
      dimension_text, perspective_card_instructions injected after brief.
    - R2: alt_frames_text injected after evidence, plus frame engagement section.
    """
    parts = []

    # Adversarial preamble — R1 only, only for the designated adversarial model
    if round_num == 1 and adversarial_model and model_id == adversarial_model:
        parts.append(_ADVERSARIAL_PREAMBLE)

    parts.append("You are participating in a multi-model deliberation. "
                 "Analyze the following brief independently and thoroughly.\n")
    parts.append(f"## Brief\n\n{brief}\n")

    # R1 injections: dimension text and perspective card instructions after brief
    if round_num == 1 and dimension_text:
        parts.append(f"## Dimension Focus\n\n{dimension_text}\n")

    if round_num == 1 and perspective_card_instructions:
        parts.append(f"## Perspective Card\n\n{perspective_card_instructions}\n")

    if round_num >= 2 and prior_views:
        parts.append("## Prior Round Views\n")
        parts.append("Other models provided these analyses in the previous round. "
                     "Consider their arguments but form your own independent judgment.\n")
        for model, view in prior_views.items():
            parts.append(f"### {model}\n{view}\n")

    if round_num >= 2 and evidence_text:
        parts.append(_EVIDENCE_HEADER)
        parts.append(f"{evidence_text}\n")

    # R2+: inject alternative frames after evidence (visible in R2, R3, R4)
    if round_num >= 2 and alt_frames_text:
        parts.append(f"## Alternative Frames\n\n{alt_frames_text}\n")

    if round_num >= 2 and unaddressed_arguments:
        parts.append("## Unaddressed Arguments From Prior Rounds\n")
        parts.append("The following arguments were raised but NOT substantively engaged with. "
                     "You MUST engage with each one — agree, rebut, or refine.\n")
        parts.append(f"{unaddressed_arguments}\n")

    # R2: frame engagement requirements
    if round_num == 2 and alt_frames_text:
        parts.append(_FRAME_ENGAGEMENT_SECTION)

    parts.append("\n## Your Analysis\n")
    parts.append("Provide your independent assessment. Structure your response as:\n"
                 "1. Key findings\n"
                 "2. Your position (with confidence: HIGH/MEDIUM/LOW)\n"
                 "3. Key arguments supporting your position\n"
                 "4. Risks or uncertainties\n")

    # Search request appendix — R1 and R2 only (not the final round)
    if not is_last_round:
        parts.append(_SEARCH_REQUEST_SECTION)

    return "\n".join(parts)


@pipeline_stage(
    name="Deliberation Round",
    description="Calls all models for a round in parallel. R1: brief only (4 models). R2: brief + R1 views + evidence + unaddressed args (3 models). R3: final convergence (2 models). Models include search request appendix (0-5 queries) in R1 and R2.",
    stage_type="round",
    order=2,
    provider="r1, reasoner, glm5, kimi (topology narrows 4→3→2)",
    inputs=["brief", "prior_views", "evidence_text", "unaddressed_arguments"],
    outputs=["responses (dict[model, text])", "responded (list)", "failed (list)"],
    prompt="""R1 PROMPT:
You are participating in a multi-model deliberation.
Analyze the following brief independently and thoroughly.

## Brief
{brief}

## Your Analysis
1. Key findings
2. Your position (with confidence: HIGH/MEDIUM/LOW)
3. Key arguments supporting your position
4. Risks or uncertainties

## Search Requests (optional, 0-5)
SEARCH_REQUESTS:
1. [specific, searchable query]
(or NONE)

---
R2+ PROMPT adds:
## Prior Round Views (all models from previous round)
## Web-Verified Evidence (AUTHORITATIVE — outranks model opinions)
## Unaddressed Arguments (You MUST engage with each one)

R3 (final round): no search request section.""",
    logic="All models called in parallel. Any model failure = BrainError (zero tolerance).",
    failure_mode="Any model failure: BrainError raised by Brain orchestrator. Zero tolerance.",
    cost="R1: ~$0.40 (4 models) | R2: ~$0.30 (3 models) | R3: ~$0.20 (2 models)",
    stage_id="round",
)
async def execute_round(
    client,
    round_num: int,
    brief: str,
    prior_views: dict[str, str] | None = None,
    evidence_text: str = "",
    unaddressed_arguments: str = "",
    is_last_round: bool = False,
    adversarial_model: str = "",
    alt_frames_text: str = "",
    dimension_text: str = "",
    perspective_card_instructions: str = "",
) -> RoundResult:
    """Execute a single deliberation round.

    Calls all models for this round in parallel. Returns a RoundResult
    with successful responses and a list of failed models.
    """
    models = ROUND_TOPOLOGY[round_num]

    # R1: build per-model prompts (adversarial model gets different preamble)
    # R2+: shared prompt with frames injection
    if round_num == 1 and adversarial_model:
        # Per-model prompts for R1 when adversarial is active
        tasks = {}
        for model in models:
            prompt = build_round_prompt(
                round_num=round_num,
                brief=brief,
                prior_views=prior_views or {},
                evidence_text=evidence_text,
                unaddressed_arguments=unaddressed_arguments,
                is_last_round=is_last_round,
                adversarial_model=adversarial_model,
                model_id=model,
                dimension_text=dimension_text,
                perspective_card_instructions=perspective_card_instructions,
            )
            tasks[model] = client.call(model, prompt)
    else:
        prompt = build_round_prompt(
            round_num=round_num,
            brief=brief,
            prior_views=prior_views or {},
            evidence_text=evidence_text,
            unaddressed_arguments=unaddressed_arguments,
            is_last_round=is_last_round,
            alt_frames_text=alt_frames_text,
            dimension_text=dimension_text,
            perspective_card_instructions=perspective_card_instructions,
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
