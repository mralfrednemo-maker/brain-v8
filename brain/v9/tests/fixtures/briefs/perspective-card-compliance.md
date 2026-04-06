# DOD §7.2-7.3 Compliance Problem: Perspective Cards on Large Briefs

## Task

Propose concrete, implementable solutions to the following engineering problem. Evaluate trade-offs and recommend the best approach.

## Background — Verified Facts (not assumptions)

We operate a multi-model deliberation pipeline ("the Brain") with 4 models in Round 1: DeepSeek-R1, DeepSeek-Reasoner, GLM-5-Turbo, and Kimi-K2. "R1" in this context means "Round 1 of deliberation" — all 4 are Round 1 models.

Our DOD (Definition of Done) specification §7.2 requires: "Exactly 4 R1 cards exist (one per R1 model)" with "All 5 structured fields present on each card." §7.3 says: "Missing card or field → ERROR."

## The Observed Problem — Verified by 20 rounds of testing

On briefs exceeding ~100k characters, 3 of 4 models consistently fail to include the 5 required structured fields (PRIMARY_FRAME, HIDDEN_ASSUMPTION_ATTACKED, STAKEHOLDER_LENS, TIME_HORIZON, FAILURE_MODE) in their output. Only DeepSeek-Reasoner reliably includes them. The other models produce substantive analysis but ignore the format instructions.

This is a known, reproducible behavior — not an assumption. It has been observed in rounds 6-20 of self-review testing.

Enforcing the DOD strictly makes the pipeline unusable for briefs >100k. We currently use a majority threshold (≥50% valid cards) as a workaround, which keeps the pipeline running but violates DOD §7.2.

## Engineering Constraints — These are decisions, not assumptions

1. The models are external APIs — we cannot fine-tune them
2. Brief size cannot go below ~100k for code-review use cases
3. Fields are extracted via regex from free-text output (no function calling available)
4. We CAN add secondary LLM calls (e.g., Sonnet at ~10-30s) after R1 to extract missing fields. We will NOT re-run the full R1 analysis pass (~2-3 min per model)
5. The 5 fields are used downstream in proof.json and coverage obligation tracking — they have real functional purpose
6. The DOD is internally owned and can be amended if well-justified
7. Post-hoc LLM extraction produces "inferred" fields, not "native" — this is acceptable if documented and flagged in proof.json with a provenance marker (e.g., `extraction_method: "inferred"` vs `"native"`)

## Solution Directions to Evaluate

1. **Post-hoc extraction via Sonnet** — For models missing fields, send their R1 output to Sonnet with: "Read this analysis and extract the 5 perspective card fields"
2. **Prompt engineering** — Move field instructions to top of prompt, repeat them, use XML tags, use few-shot examples
3. **DOD amendment** — Change §7.2 to require majority compliance with documented justification for missing cards
4. **Card-only follow-up** — After R1, if fields missing, send a SHORT prompt to the same model: "Based on your analysis, fill in: PRIMARY_FRAME: ..."
5. **Hybrid** — Combine approaches

## What I Need

For each viable solution: (1) concrete implementation sketch, (2) DOD compliance level, (3) trade-offs, (4) risk of changing analytical outcome.

Recommend the best solution with rationale.

---

## DOD §7 — Perspective Cards (verbatim from DOD-V3.md)

### 7.1 Required Schema

proof.perspective_cards SHALL contain one entry per R1 model:

| Field | Type |
|---|---|
| model_id | string |
| primary_frame | string |
| hidden_assumption_attacked | string |
| stakeholder_lens | string |
| time_horizon | enum (SHORT, MEDIUM, LONG) |
| failure_mode | string |
| coverage_obligation | enum (CONTRARIAN, MECHANISM_ANALYSIS, OPERATIONAL_RISK, OBJECTIVE_REFRAMING) |
| dimensions_addressed | array[string] |

### 7.2 Requirements

- Exactly 4 R1 cards exist (one per R1 model)
- All 5 structured fields present on each card
- Distinct coverage_obligation assigned across the 4 models

### 7.3 Failure Modes

| Failure | Outcome |
|---|---|
| Missing card or field | ERROR |
| Coverage obligation not assigned | ERROR |

---

## Source Code: perspective_cards.py (complete)

```python
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
    "primary_frame": re.compile(r"PRIMARY_FRAME:\s*\**(.+?)\**\s*$", re.IGNORECASE | re.MULTILINE),
    "hidden_assumption_attacked": re.compile(r"HIDDEN_ASSUMPTION_ATTACKED:\s*\**(.+?)\**\s*$", re.IGNORECASE | re.MULTILINE),
    "stakeholder_lens": re.compile(r"STAKEHOLDER_LENS:\s*\**(.+?)\**\s*$", re.IGNORECASE | re.MULTILINE),
    "time_horizon": re.compile(r"TIME_HORIZON:\s*\**(\w+)\**", re.IGNORECASE),
    "failure_mode": re.compile(r"FAILURE_MODE:\s*\**(.+?)\**\s*$", re.IGNORECASE | re.MULTILINE),
}


def _parse_time_horizon(text: str) -> TimeHorizon:
    text = text.strip().upper()
    if text in ("SHORT", "SHORT-TERM", "SHORT_TERM"):
        return TimeHorizon.SHORT
    elif text in ("LONG", "LONG-TERM", "LONG_TERM"):
        return TimeHorizon.LONG
    return TimeHorizon.MEDIUM


def extract_perspective_cards(r1_texts: dict[str, str]) -> list[PerspectiveCard]:
    """Extract perspective cards from R1 model outputs.

    DOD §7.3: "Missing card or field → ERROR"
    """
    from thinker.types import BrainError

    cards = []
    noncompliant_models = []
    required_fields = ["primary_frame", "hidden_assumption_attacked",
                       "stakeholder_lens", "time_horizon", "failure_mode"]

    for model_id, text in r1_texts.items():
        fields = {}
        for field_name, pattern in _FIELD_PATTERNS.items():
            match = pattern.search(text)
            if match:
                fields[field_name] = match.group(1).strip()

        # DOD §7.3 + zero-tolerance: missing card or field → ERROR
        if not text.strip():
            raise BrainError(
                "perspective_cards",
                f"Model {model_id} produced no R1 output — zero tolerance",
                detail="DOD §7.3: Missing card → ERROR.",
            )
        missing = [f for f in required_fields if not fields.get(f)]
        if missing:
            # Track non-compliant models; enforce minimum card count after loop
            noncompliant_models.append((model_id, missing))
            continue

        time_horizon = _parse_time_horizon(fields["time_horizon"])
        obligation = _MODEL_OBLIGATIONS.get(model_id, CoverageObligation.MECHANISM_ANALYSIS)

        card = PerspectiveCard(
            model_id=model_id,
            primary_frame=fields["primary_frame"],
            hidden_assumption_attacked=fields["hidden_assumption_attacked"],
            stakeholder_lens=fields["stakeholder_lens"],
            time_horizon=time_horizon,
            failure_mode=fields["failure_mode"],
            coverage_obligation=obligation,
        )
        cards.append(card)

    # DOD §7.2: "Exactly 4 R1 cards exist (one per R1 model)"
    # DOD §7.3: Missing card → ERROR
    # Relaxed: majority compliance (≥50% models) — large briefs break structured output
    # on weaker models (GLM5, Kimi). See round 20 failure. Brain asked to propose fix.
    min_required = max(2, len(r1_texts) // 2)
    if len(cards) < min_required:
        nc_details = "; ".join(f"{m}: missing {f}" for m, f in noncompliant_models)
        raise BrainError(
            "perspective_cards",
            f"Only {len(cards)}/{len(r1_texts)} models produced valid perspective cards "
            f"(minimum {min_required} required)",
            detail=f"DOD §7.3: Missing card → ERROR. Non-compliant: {nc_details}",
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
```

## Source Code: rounds.py — R1 prompt construction (relevant excerpt)

```python
def build_round_prompt(
    round_num: int,
    brief: str,
    prior_views: str = "",
    evidence_text: str = "",
    unaddressed_arguments: str = "",
    is_last_round: bool = False,
    adversarial_model: str = "",
    model_id: str = "",
    alt_frames_text: str = "",
    dimension_text: str = "",
    perspective_card_instructions: str = "",
) -> str:
    parts = []

    # Adversarial preamble — R1 only, only for the designated adversarial model
    # ...

    parts.append("You are participating in a multi-model deliberation. "
                 "Analyze the following brief independently and thoroughly.\n")

    # R1: perspective card instructions BEFORE brief (so models see them even on huge briefs)
    if round_num == 1 and perspective_card_instructions:
        parts.append(f"## MANDATORY Structured Output (include at END of your response)\n\n{perspective_card_instructions}\n")

    if round_num == 1 and dimension_text:
        parts.append(f"## Dimension Focus\n\n{dimension_text}\n")

    parts.append(f"## Brief\n\n{brief}\n")
    # ... rest of prompt construction
```

## Source Code: config.py — Model definitions

```python
R1_MODEL = ModelConfig("r1", "deepseek/deepseek-r1-0528", "openrouter", 30_000, 720, is_thinking=True)
REASONER_MODEL = ModelConfig("reasoner", "deepseek-reasoner", "deepseek", 30_000, 720, is_thinking=True)
GLM5_MODEL = ModelConfig("glm5", "glm-5-turbo", "zai", 16_000, 480)
KIMI_MODEL = ModelConfig("kimi", "moonshotai/kimi-k2", "openrouter", 16_000, 480)
SONNET_MODEL = ModelConfig("sonnet", "claude-sonnet-4-6", "anthropic", 16_000, 300)

ROUND_TOPOLOGY: dict[int, list[str]] = {
    1: ["r1", "reasoner", "glm5", "kimi"],
    2: ["r1", "reasoner", "glm5"],
    3: ["r1", "reasoner"],
    4: ["r1", "reasoner"],
}
```
