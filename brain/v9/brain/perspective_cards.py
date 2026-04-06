"""Perspective Cards - structured R1 output extraction (DoD v3.0 Section 7).

Parses R1 model outputs to extract 5 structured fields per model.
Primary: regex extraction from R1 output (native).
Fallback: post-hoc LLM extraction via Haiku -> Sonnet (inferred).
DOD Section 7.2: Exactly 4 cards required. DOD Section 7.3: Missing card -> ERROR.
"""
from __future__ import annotations

import asyncio
import re

from brain.types import CoverageObligation, PerspectiveCard, TimeHorizon

# Coverage obligation assignments (fixed per model)
_MODEL_OBLIGATIONS = {
    "kimi": CoverageObligation.CONTRARIAN,
    "r1": CoverageObligation.MECHANISM_ANALYSIS,
    "reasoner": CoverageObligation.OPERATIONAL_RISK,
    "glm5": CoverageObligation.OBJECTIVE_REFRAMING,
}

REQUIRED_FIELDS = ["primary_frame", "hidden_assumption_attacked",
                   "stakeholder_lens", "time_horizon", "failure_mode"]

# Field patterns to extract from model output
_FIELD_PATTERNS = {
    "primary_frame": re.compile(r"PRIMARY_FRAME:\s*\**(.+?)\**\s*$", re.IGNORECASE | re.MULTILINE),
    "hidden_assumption_attacked": re.compile(r"HIDDEN_ASSUMPTION_ATTACKED:\s*\**(.+?)\**\s*$", re.IGNORECASE | re.MULTILINE),
    "stakeholder_lens": re.compile(r"STAKEHOLDER_LENS:\s*\**(.+?)\**\s*$", re.IGNORECASE | re.MULTILINE),
    "time_horizon": re.compile(r"TIME_HORIZON:\s*\**(\w+)\**", re.IGNORECASE),
    "failure_mode": re.compile(r"FAILURE_MODE:\s*\**(.+?)\**\s*$", re.IGNORECASE | re.MULTILINE),
}

_EXTRACTION_PROMPT = """Read the following model analysis and extract the 5 perspective card fields.
The model was asked to include these fields but failed to do so. Infer them from the content of the analysis.

RULES:
- PRIMARY_FRAME: The model's primary analytical lens or way of looking at the question
- HIDDEN_ASSUMPTION_ATTACKED: Which assumption the model is challenging or questioning
- STAKEHOLDER_LENS: Whose perspective the model is representing
- TIME_HORIZON: SHORT, MEDIUM, or LONG - based on the timeframe of the analysis
- FAILURE_MODE: What could go wrong with the model's recommended approach

Output EXACTLY these 5 lines and nothing else:
PRIMARY_FRAME: <value>
HIDDEN_ASSUMPTION_ATTACKED: <value>
STAKEHOLDER_LENS: <value>
TIME_HORIZON: <SHORT|MEDIUM|LONG>
FAILURE_MODE: <value>

--- MODEL ANALYSIS (first and last sections) ---

{text}"""


def _truncate_for_extraction(text: str, max_chars: int = 8000) -> str:
    """Truncate R1 output to first/last segments for extraction context."""
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    return text[:half] + "\n\n[... middle truncated ...]\n\n" + text[-half:]


def _parse_time_horizon(text: str) -> TimeHorizon:
    text = text.strip().upper()
    if text in ("SHORT", "SHORT-TERM", "SHORT_TERM"):
        return TimeHorizon.SHORT
    elif text in ("LONG", "LONG-TERM", "LONG_TERM"):
        return TimeHorizon.LONG
    return TimeHorizon.MEDIUM


def _extract_fields_regex(text: str) -> dict[str, str]:
    """Try to extract fields via regex. Returns dict of found fields."""
    fields = {}
    for field_name, pattern in _FIELD_PATTERNS.items():
        match = pattern.search(text)
        if match:
            fields[field_name] = match.group(1).strip()
    return fields


async def _extract_fields_llm(client, model_name: str, r1_text: str) -> dict[str, str] | None:
    """Extract missing fields via LLM. Returns dict of fields or None on failure."""
    truncated = _truncate_for_extraction(r1_text)
    prompt = _EXTRACTION_PROMPT.format(text=truncated)
    resp = await client.call(model_name, prompt)
    if not resp.ok:
        return None
    return _extract_fields_regex(resp.text)


def _build_card(model_id: str, fields: dict[str, str], provenance: dict[str, str]) -> PerspectiveCard:
    """Build a PerspectiveCard from extracted fields."""
    return PerspectiveCard(
        model_id=model_id,
        primary_frame=fields.get("primary_frame", ""),
        hidden_assumption_attacked=fields.get("hidden_assumption_attacked", ""),
        stakeholder_lens=fields.get("stakeholder_lens", ""),
        time_horizon=_parse_time_horizon(fields.get("time_horizon", "MEDIUM")),
        failure_mode=fields.get("failure_mode", ""),
        coverage_obligation=_MODEL_OBLIGATIONS.get(model_id, CoverageObligation.MECHANISM_ANALYSIS),
        field_provenance=provenance,
    )


async def extract_perspective_cards(r1_texts: dict[str, str], llm_client=None) -> list[PerspectiveCard]:
    """Extract perspective cards from R1 model outputs.

    Phase 1: regex extraction (native).
    Phase 2: for models with missing fields, post-hoc LLM extraction via Haiku -> Sonnet.
    DOD Section 7.2: Exactly N cards required (one per R1 model).
    DOD Section 7.3: Missing card -> ERROR.
    """
    from brain.types import BrainError

    cards = []
    needs_extraction: list[tuple[str, str, dict[str, str]]] = []  # (model_id, text, native_fields)

    # Phase 1: regex extraction
    for model_id, text in r1_texts.items():
        if not text.strip():
            raise BrainError(
                "perspective_cards",
                f"Model {model_id} produced no R1 output - zero tolerance",
                detail="DOD Section 7.3: Missing card -> ERROR.",
            )

        fields = _extract_fields_regex(text)
        missing = [f for f in REQUIRED_FIELDS if not fields.get(f)]

        if not missing:
            # All fields found natively
            provenance = {f: "native" for f in REQUIRED_FIELDS}
            cards.append(_build_card(model_id, fields, provenance))
        else:
            # Track for Phase 2
            needs_extraction.append((model_id, text, fields))

    # Phase 2: post-hoc LLM extraction for models with missing fields
    if needs_extraction and llm_client:
        async def _extract_one(model_id: str, text: str, native_fields: dict[str, str]) -> PerspectiveCard | None:
            merged = dict(native_fields)
            provenance = {f: "native" for f in REQUIRED_FIELDS if native_fields.get(f)}

            # Try Haiku first, Sonnet as fallback
            for extractor in ("haiku", "sonnet"):
                inferred = await _extract_fields_llm(llm_client, extractor, text)
                if inferred:
                    # Merge: native fields take priority, fill other gaps with inferred values.
                    for f in REQUIRED_FIELDS:
                        if merged.get(f):
                            continue
                        if f != "hidden_assumption_attacked" and inferred.get(f):
                            merged[f] = inferred[f]
                            provenance[f] = f"inferred:{extractor}"

            if not merged.get("hidden_assumption_attacked"):
                merged["hidden_assumption_attacked"] = "NOT_STATED"
                provenance["hidden_assumption_attacked"] = "not_stated"

            still_missing = [f for f in REQUIRED_FIELDS if not merged.get(f)]
            if not still_missing:
                return _build_card(model_id, merged, provenance)

            return None

        tasks = [_extract_one(mid, txt, nf) for mid, txt, nf in needs_extraction]
        results = await asyncio.gather(*tasks)

        failed_models = []
        for (model_id, _, _), result in zip(needs_extraction, results):
            if result:
                cards.append(result)
            else:
                failed_models.append(model_id)

        if failed_models:
            raise BrainError(
                "perspective_cards",
                f"Failed to extract perspective cards for: {failed_models} "
                f"(regex and LLM extraction both failed)",
                detail=f"DOD Section 7.2-7.3: All {len(r1_texts)} cards required. "
                       f"Post-hoc extraction via Haiku+Sonnet could not produce valid fields.",
            )

    elif needs_extraction and not llm_client:
        # No LLM client - fall back to majority threshold (legacy mode)
        min_required = max(2, len(r1_texts) // 2)
        if len(cards) < min_required:
            nc_models = [mid for mid, _, _ in needs_extraction]
            raise BrainError(
                "perspective_cards",
                f"Only {len(cards)}/{len(r1_texts)} models produced valid perspective cards "
                f"(minimum {min_required} required, no LLM client for post-hoc extraction)",
                detail=f"DOD Section 7.3: Missing card -> ERROR. Non-compliant: {nc_models}",
            )

    # DOD Section 7.2: exactly N cards required
    if len(cards) != len(r1_texts):
        raise BrainError(
            "perspective_cards",
            f"Only {len(cards)}/{len(r1_texts)} perspective cards produced",
            detail="DOD Section 7.2: Exactly one card per R1 model required.",
        )

    return cards


def format_perspective_card_instructions() -> str:
    """Generate the perspective card instruction text for R1 prompts."""
    return (
        "\n## Structured Output Requirements (MANDATORY)\n"
        "After your analysis, you MUST include these 5 fields on separate lines:\n\n"
        "PRIMARY_FRAME: [your primary way of looking at this question]\n"
        "HIDDEN_ASSUMPTION_ATTACKED: [which assumption you are challenging]\n"
        "STAKEHOLDER_LENS: [whose perspective you are representing]\n"
        "TIME_HORIZON: [SHORT | MEDIUM | LONG]\n"
        "FAILURE_MODE: [what could go wrong with your recommended approach]\n"
    )
