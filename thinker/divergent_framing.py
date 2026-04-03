"""Divergent Framing — framing pass, frame survival, exploration stress (DoD v3.0 Section 8).

Framing pass: Sonnet extracts alt frames from R1 outputs.
Frame survival: 3-vote R2 drop (traceable), CONTESTED in R3/R4 (never dropped).
Exploration stress: inject seed frames when R1 agreement > 0.75 on OPEN/HIGH.
"""
from __future__ import annotations

import json
from typing import Optional

from thinker.pipeline import pipeline_stage
from thinker.types import (
    BrainError, CrossDomainAnalogy, DivergenceResult, FrameInfo,
    FrameSurvivalStatus, FrameType, QuestionClass, StakesClass,
)

FRAMING_EXTRACT_PROMPT = """You are a framing analyst for a multi-model deliberation system.

Given the R1 model outputs below, extract ALL material alternative frames (ways of looking at this question that differ from the obvious framing).

## Brief
{brief}

## R1 Model Outputs
{r1_texts_formatted}

## Output Format — STRICT JSON (no markdown, no commentary)

{{
  "frames": [
    {{
      "frame_id": "FRAME-1",
      "text": "description of the alternative frame",
      "origin_model": "model_id that proposed this",
      "frame_type": "INVERSION | OBJECTIVE_REWRITE | PREMISE_CHALLENGE | CROSS_DOMAIN_ANALOGY | OPPOSITE_STANCE | REMOVE_PROBLEM",
      "material_to_outcome": true/false
    }}
  ],
  "cross_domain_analogies": [
    {{
      "analogy_id": "ANA-1",
      "source_domain": "domain the analogy comes from",
      "target_claim_id": "claim this analogy supports/challenges",
      "transfer_mechanism": "how the analogy applies"
    }}
  ]
}}

## Rules
- Extract frames that are genuinely different from the default framing
- A frame is material if it could change the outcome
- Cross-domain analogies: look for when models draw parallels from other fields
- Be generous: if in doubt, include it as a frame"""


FRAME_SURVIVAL_PROMPT = """Evaluate whether each alternative frame survives this round of deliberation.

## Active Frames
{frames_formatted}

## Round {round_num} Model Outputs
{round_texts_formatted}

## Output Format — STRICT JSON

{{
  "evaluations": [
    {{
      "frame_id": "FRAME-1",
      "status": "ACTIVE | CONTESTED | DROPPED | ADOPTED | REBUTTED",
      "drop_vote_models": ["model_id"],
      "reasoning": "why this status"
    }}
  ]
}}

## Rules (Round {round_num})
{survival_rules}"""


@pipeline_stage(
    name="Framing Pass",
    description="Sonnet extracts alternative frames from R1 outputs. Tracks frame survival through rounds.",
    stage_type="track",
    order=5,
    provider="sonnet",
    inputs=["brief", "r1_texts"],
    outputs=["DivergenceResult"],
    logic="Extract frames. Track survival. 3-vote R2 drop. CONTESTED never dropped in R3/R4.",
    failure_mode="LLM failure or parse failure: BrainError.",
    cost="1-3 Sonnet calls",
    stage_id="framing_pass",
)
async def run_framing_extract(client, brief: str, r1_texts: dict[str, str]) -> DivergenceResult:
    """Extract alternative frames from R1 outputs."""
    # Format R1 texts
    r1_formatted = "\n\n".join(f"### {model}\n{text}" for model, text in r1_texts.items())
    prompt = FRAMING_EXTRACT_PROMPT.format(brief=brief, r1_texts_formatted=r1_formatted)

    resp = await client.call("sonnet", prompt)
    if not resp.ok:
        raise BrainError("framing_pass", f"Framing extract LLM call failed: {resp.error}")

    text = resp.text.strip()
    if text.startswith("```"):
        text = "\n".join(text.split("\n")[1:])
    if text.endswith("```"):
        text = "\n".join(text.split("\n")[:-1])
    text = text.strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise BrainError("framing_pass", f"Failed to parse framing extract JSON: {e}",
                         detail=resp.text[:500])

    frames = []
    for f in data.get("frames", []):
        try:
            frame_type = FrameType(f.get("frame_type", "INVERSION"))
        except ValueError:
            frame_type = FrameType.INVERSION
        frames.append(FrameInfo(
            frame_id=f.get("frame_id", f"FRAME-{len(frames)+1}"),
            text=f.get("text", ""),
            origin_round=1,
            origin_model=f.get("origin_model", ""),
            frame_type=frame_type,
            material_to_outcome=f.get("material_to_outcome", True),
        ))

    analogies = []
    for a in data.get("cross_domain_analogies", []):
        analogies.append(CrossDomainAnalogy(
            analogy_id=a.get("analogy_id", f"ANA-{len(analogies)+1}"),
            source_domain=a.get("source_domain", ""),
            target_claim_id=a.get("target_claim_id", ""),
            transfer_mechanism=a.get("transfer_mechanism", ""),
        ))

    return DivergenceResult(
        required=True,
        framing_pass_executed=True,
        alt_frames=frames,
        cross_domain_analogies=analogies,
    )


async def run_frame_survival_check(
    client,
    frames: list[FrameInfo],
    round_texts: dict[str, str],
    round_num: int,
    is_analysis_mode: bool = False,
) -> list[FrameInfo]:
    """Check frame survival against a round's outputs.

    R2: frame DROPPED only if 3+ traceable drop votes.
    R3/R4: frames are never dropped, only CONTESTED.
    """
    if not frames:
        return frames

    active_frames = [f for f in frames if f.survival_status in
                     (FrameSurvivalStatus.ACTIVE, FrameSurvivalStatus.CONTESTED)]
    if not active_frames:
        return frames

    frames_formatted = "\n".join(
        f"- {f.frame_id}: {f.text} (status: {f.survival_status.value})"
        for f in active_frames
    )
    round_formatted = "\n\n".join(f"### {m}\n{t}" for m, t in round_texts.items())

    if round_num == 2:
        rules = "- A frame is DROPPED only if 3 or more models explicitly reject it with traceable reasoning.\n- A frame is CONTESTED if at least 1 model challenges it but fewer than 3.\n- A frame is ADOPTED if a model explicitly takes it up.\n- A frame is REBUTTED if substantively countered."
    else:
        rules = "- Frames are NEVER dropped in R3/R4. They can only be CONTESTED, ADOPTED, or remain ACTIVE.\n- CONTESTED frames stay CONTESTED (never downgraded to DROPPED)."

    prompt = FRAME_SURVIVAL_PROMPT.format(
        frames_formatted=frames_formatted,
        round_num=round_num,
        round_texts_formatted=round_formatted,
        survival_rules=rules,
    )

    resp = await client.call("sonnet", prompt)
    if not resp.ok:
        raise BrainError(f"frame_survival_r{round_num}",
                         f"Frame survival LLM call failed: {resp.error}")

    text = resp.text.strip()
    if text.startswith("```"):
        text = "\n".join(text.split("\n")[1:])
    if text.endswith("```"):
        text = "\n".join(text.split("\n")[:-1])
    text = text.strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise BrainError(f"frame_survival_r{round_num}",
                         f"Failed to parse frame survival JSON: {e}",
                         detail=resp.text[:500])

    # Build lookup
    eval_lookup = {e["frame_id"]: e for e in data.get("evaluations", [])}

    for frame in frames:
        ev = eval_lookup.get(frame.frame_id)
        if not ev:
            continue

        try:
            new_status = FrameSurvivalStatus(ev.get("status", "ACTIVE"))
        except ValueError:
            new_status = FrameSurvivalStatus.ACTIVE

        # ANALYSIS mode: frames are NEVER dropped (DOD 18.2)
        if is_analysis_mode and new_status == FrameSurvivalStatus.DROPPED:
            new_status = FrameSurvivalStatus.CONTESTED

        # R3/R4: never allow DROPPED
        if round_num >= 3 and new_status == FrameSurvivalStatus.DROPPED:
            new_status = FrameSurvivalStatus.CONTESTED

        # R2: require 3 drop votes for DROPPED
        if round_num == 2 and new_status == FrameSurvivalStatus.DROPPED:
            drop_models = ev.get("drop_vote_models", [])
            if len(drop_models) < 3:
                new_status = FrameSurvivalStatus.CONTESTED
            else:
                frame.r2_drop_vote_count = len(drop_models)
                frame.r2_drop_vote_refs = drop_models

        frame.survival_status = new_status

    return frames


def check_exploration_stress(
    agreement_ratio: float,
    question_class: QuestionClass,
    stakes_class: StakesClass,
) -> bool:
    """Check if exploration stress trigger should fire.

    Returns True if R1 agreement > 0.75 on OPEN/HIGH questions.
    """
    if agreement_ratio <= 0.75:
        return False
    # DOD Section 8.3: OPEN OR HIGH (not AMBIGUOUS)
    if question_class == QuestionClass.OPEN:
        return True
    if stakes_class == StakesClass.HIGH:
        return True
    return False


def format_frames_for_prompt(frames: list[FrameInfo]) -> str:
    """Format active/contested frames for injection into R2+ prompts."""
    active = [f for f in frames if f.survival_status in
              (FrameSurvivalStatus.ACTIVE, FrameSurvivalStatus.CONTESTED)]
    if not active:
        return ""

    lines = ["## Alternative Frames (must address)",
             "The following alternative frames have survived deliberation so far.\n"]
    for f in active:
        status_tag = f" [{f.survival_status.value}]" if f.survival_status == FrameSurvivalStatus.CONTESTED else ""
        lines.append(f"- **{f.frame_id}**: {f.text}{status_tag}")

    return "\n".join(lines)


def format_r2_frame_enforcement() -> str:
    """R2 frame enforcement instruction text."""
    return (
        "\n## Frame Engagement Requirements (MANDATORY for R2)\n"
        "You MUST:\n"
        "1. ADOPT at least one alternative frame and argue from its perspective\n"
        "2. REBUT at least one alternative frame with substantive counter-arguments\n"
        "3. GENERATE at least one NEW alternative frame not yet proposed\n"
        "\nFor each, clearly label: ADOPT: [frame_id], REBUT: [frame_id], NEW_FRAME: [description]\n"
    )
