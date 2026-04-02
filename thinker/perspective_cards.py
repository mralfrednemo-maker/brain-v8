"""Perspective Cards — structured R1 output extraction (DoD v3.0 Section 7).

Parses R1 model outputs to extract 5 structured fields per model.
No LLM call — regex/text parsing only.
"""
from __future__ import annotations

import re

from thinker.types import CoverageObligation, PerspectiveCard, TimeHorizon

# Coverage obligation assignments (fixed per model)
_MODEL_OBLIGATIONS = {
    "kimi": CoverageObligation.CONTRARIAN,
    "r1": CoverageObligation.MECHANISM_ANALYSIS,
    "reasoner": CoverageObligation.OPERATIONAL_RISK,
    "glm5": CoverageObligation.OBJECTIVE_REFRAMING,
}

# Field patterns to extract from model output
_FIELD_PATTERNS = {
    "primary_frame": re.compile(r"PRIMARY_FRAME:\s*(.+)", re.IGNORECASE),
    "hidden_assumption_attacked": re.compile(r"HIDDEN_ASSUMPTION_ATTACKED:\s*(.+)", re.IGNORECASE),
    "stakeholder_lens": re.compile(r"STAKEHOLDER_LENS:\s*(.+)", re.IGNORECASE),
    "time_horizon": re.compile(r"TIME_HORIZON:\s*(\w+)", re.IGNORECASE),
    "failure_mode": re.compile(r"FAILURE_MODE:\s*(.+)", re.IGNORECASE),
}


def _parse_time_horizon(text: str) -> TimeHorizon:
    text = text.strip().upper()
    if text in ("SHORT", "SHORT-TERM", "SHORT_TERM"):
        return TimeHorizon.SHORT
    elif text in ("LONG", "LONG-TERM", "LONG_TERM"):
        return TimeHorizon.LONG
    return TimeHorizon.MEDIUM


def extract_perspective_cards(r1_texts: dict[str, str]) -> list[PerspectiveCard]:
    """Extract perspective cards from R1 model outputs."""
    cards = []
    for model_id, text in r1_texts.items():
        fields = {}
        for field_name, pattern in _FIELD_PATTERNS.items():
            match = pattern.search(text)
            if match:
                fields[field_name] = match.group(1).strip()

        time_horizon = _parse_time_horizon(fields.get("time_horizon", "MEDIUM"))
        obligation = _MODEL_OBLIGATIONS.get(model_id, CoverageObligation.MECHANISM_ANALYSIS)

        card = PerspectiveCard(
            model_id=model_id,
            primary_frame=fields.get("primary_frame", ""),
            hidden_assumption_attacked=fields.get("hidden_assumption_attacked", ""),
            stakeholder_lens=fields.get("stakeholder_lens", ""),
            time_horizon=time_horizon,
            failure_mode=fields.get("failure_mode", ""),
            coverage_obligation=obligation,
        )
        cards.append(card)

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
