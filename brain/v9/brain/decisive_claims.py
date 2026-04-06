"""Decisive Claim Extraction — identifies claims that carry the conclusion (DESIGN-V3.md Section 3.2).

One Sonnet call post-R4. Extracts claims that are material to the conclusion,
with evidence bindings showing what supports each claim.
"""
from __future__ import annotations

import json

from brain.pipeline import pipeline_stage
from brain.types import (
    BrainError, DecisiveClaim, EvidenceSupportStatus,
)

CLAIM_EXTRACTION_PROMPT = """You are a decisive claim extractor for a multi-model deliberation system.

Given the final round model outputs and available evidence, identify the 3-8 most decisive claims —
the claims that CARRY the conclusion. A decisive claim is one where, if it were false, the conclusion
would change.

## Final Round Model Outputs
{final_views}

## Available Evidence
{evidence_text}

## Output Format — STRICT JSON (no markdown, no commentary)

{{
  "claims": [
    {{
      "claim_id": "DC-1",
      "text": "the decisive claim in one sentence",
      "material_to_conclusion": true,
      "evidence_refs": ["E001", "E003"],
      "evidence_support_status": "SUPPORTED | PARTIAL | UNSUPPORTED",
      "supporting_model_ids": ["r1", "reasoner"]
    }}
  ]
}}

## Rules
- 3-8 claims maximum. Focus on the ones that MATTER.
- SUPPORTED: claim is directly backed by cited evidence
- PARTIAL: some evidence exists but doesn't fully prove the claim
- UNSUPPORTED: claim is asserted by models but has no evidence backing
- evidence_refs: list evidence IDs (E001-E999) that support this claim. Empty list = UNSUPPORTED.
- material_to_conclusion: true if removing this claim would change the outcome
- supporting_model_ids: list which models made or endorsed this claim (e.g. ["r1", "reasoner"])"""


@pipeline_stage(
    name="Decisive Claim Extraction",
    description="Post-R4 Sonnet call extracting 3-8 claims that carry the conclusion, with evidence bindings.",
    stage_type="track",
    order=16,
    provider="sonnet",
    inputs=["final_views", "evidence_text"],
    outputs=["DecisiveClaim[]"],
    logic="Parse JSON. 3-8 claims. Each with evidence refs and support status.",
    failure_mode="LLM or parse failure: return empty list (non-fatal — degrades D4/stability but doesn't halt).",
    cost="1 Sonnet call",
    stage_id="decisive_claims",
)
async def extract_decisive_claims(
    client,
    final_views: dict[str, str],
    evidence_text: str,
) -> list[DecisiveClaim]:
    """Extract decisive claims from final round outputs."""
    views_formatted = "\n\n".join(f"### {m}\n{t}" for m, t in final_views.items())
    prompt = CLAIM_EXTRACTION_PROMPT.format(
        final_views=views_formatted,
        evidence_text=evidence_text or "No evidence available.",
    )

    resp = await client.call("sonnet", prompt)
    if not resp.ok:
        # Non-fatal: decisive claims degrade gracefully
        return []

    text = resp.text.strip()
    if text.startswith("```"):
        text = "\n".join(text.split("\n")[1:])
    if text.endswith("```"):
        text = "\n".join(text.split("\n")[:-1])
    text = text.strip()

    try:
        from brain.types import extract_json
        data = extract_json(text)
    except json.JSONDecodeError:
        return []

    claims = []
    for c in data.get("claims", [])[:8]:
        try:
            support = EvidenceSupportStatus(c.get("evidence_support_status", "UNSUPPORTED"))
        except ValueError:
            support = EvidenceSupportStatus.UNSUPPORTED

        claims.append(DecisiveClaim(
            claim_id=c.get("claim_id", f"DC-{len(claims)+1}"),
            text=c.get("text", ""),
            material_to_conclusion=c.get("material_to_conclusion", True),
            evidence_refs=c.get("evidence_refs", []),
            evidence_support_status=support,
            supporting_model_ids=c.get("supporting_model_ids", []),
        ))

    return claims
