"""Dimension Seeder — pre-R1 exploration dimension generation (DoD v3.0 Section 6).

One Sonnet call generates 3-5 mandatory exploration dimensions from the brief.
Injected into all R1 prompts. Models must address all dimensions or justify irrelevance.
"""
from __future__ import annotations

import json

from thinker.pipeline import pipeline_stage
from thinker.types import BrainError, DimensionItem, DimensionSeedResult

SEEDER_PROMPT = """You are an exploration dimension generator for a multi-model deliberation system.

Given the brief below, identify 3-5 mandatory exploration dimensions that models MUST address in their analysis. Each dimension is a distinct aspect or lens through which the question should be examined.

## Brief
{brief}

## Output Format — STRICT JSON (no markdown, no commentary)

{{
  "dimensions": [
    {{
      "dimension_id": "DIM-1",
      "name": "short descriptive name",
      "mandatory": true
    }}
  ]
}}

## Rules
- Generate exactly 3-5 dimensions. No fewer than 3, no more than 5.
- Each dimension should be substantively different (not overlapping).
- Dimensions should cover: technical, organizational, risk, ethical/legal, and operational aspects as relevant.
- Use short, descriptive names (2-5 words each).
- All dimensions are mandatory=true."""


@pipeline_stage(
    name="Dimension Seeder",
    description="Pre-R1 Sonnet call generating 3-5 mandatory exploration dimensions. Injected into all R1 prompts.",
    stage_type="seeder",
    order=2,
    provider="sonnet",
    inputs=["brief"],
    outputs=["DimensionSeedResult"],
    logic="Parse JSON. 3-5 dimensions required. <3 -> BrainError.",
    failure_mode="LLM failure or parse failure or <3 dimensions: BrainError.",
    cost="1 Sonnet call",
    stage_id="dimensions",
)
async def run_dimension_seeder(client, brief: str) -> DimensionSeedResult:
    """Run the Dimension Seeder. Returns DimensionSeedResult."""
    # Truncate brief for seeder — it needs the question, not full source code
    brief_for_seeder = brief[:15000] if len(brief) > 15000 else brief
    prompt = SEEDER_PROMPT.format(brief=brief_for_seeder)
    resp = await client.call("sonnet", prompt)

    if not resp.ok:
        raise BrainError("dimension_seeder", f"Dimension Seeder LLM call failed: {resp.error}")

    text = resp.text.strip()
    if text.startswith("```"):
        text = "\n".join(text.split("\n")[1:])
    if text.endswith("```"):
        text = "\n".join(text.split("\n")[:-1])
    text = text.strip()

    try:
        from thinker.types import extract_json
        data = extract_json(text)
    except json.JSONDecodeError as e:
        raise BrainError("dimension_seeder", f"Failed to parse Dimension Seeder JSON: {e}",
                         detail=resp.text[:500])

    dims_data = data.get("dimensions", [])
    if not dims_data:
        raise BrainError("dimension_seeder", "No dimensions in response",
                         detail=resp.text[:500])

    # Cap at 5
    dims_data = dims_data[:5]

    items = []
    for d in dims_data:
        items.append(DimensionItem(
            dimension_id=d.get("dimension_id", f"DIM-{len(items)+1}"),
            name=d.get("name", "Unknown"),
            mandatory=d.get("mandatory", True),
        ))

    if len(items) < 3:
        raise BrainError("dimension_seeder",
                         f"Fewer than 3 dimensions generated ({len(items)}). DoD requires 3-5.",
                         detail=f"Got: {[d.name for d in items]}")

    return DimensionSeedResult(
        seeded=True,
        parse_ok=True,
        items=items,
        dimension_count=len(items),
        dimension_coverage_score=0.0,
    )


def format_dimensions_for_prompt(dimensions: list[DimensionItem]) -> str:
    """Format dimensions for injection into R1 prompts."""
    lines = ["## Mandatory Exploration Dimensions",
             "You MUST address ALL of the following dimensions in your analysis.",
             "If a dimension is genuinely irrelevant, explain why.\n"]
    for d in dimensions:
        lines.append(f"- **{d.dimension_id}: {d.name}**")
    return "\n".join(lines)
