"""PreflightAssessment — merged Gate 1 + CS Audit (DoD v3.0 Section 4).

Single Sonnet call. Handles admission, modality selection, effort calibration,
defect typing, hidden-context discovery, assumption surfacing, and search scope.

Replaces the separate gate1.py for V9. gate1.py is kept for backward compat
but preflight.py is the canonical admission stage.
"""
from __future__ import annotations

import json

from thinker.pipeline import pipeline_stage
from thinker.types import (
    Answerability, AssumptionVerifiability, BrainError, CriticalAssumption,
    EffortTier, HiddenContextGap, Modality, PremiseFlag, PremiseFlagRouting,
    PremiseFlagSeverity, PremiseFlagType, PreflightResult, QuestionClass,
    SearchScope, StakesClass,
)

PREFLIGHT_PROMPT = """You are a preflight assessor for a multi-model deliberation system.

Analyze the brief below and produce a structured JSON assessment. Your job is to:
1. Determine if the brief is answerable as-is
2. Classify the question type, stakes, and required effort
3. Detect premise defects, hidden context gaps, and critical assumptions
4. Recommend search scope and modality (DECIDE vs ANALYSIS)

## Brief
{brief}

## Output Format — STRICT JSON (no markdown, no commentary, just the JSON object)

{{
  "answerability": "ANSWERABLE | NEED_MORE | INVALID_FORM",
  "question_class": "TRIVIAL | WELL_ESTABLISHED | OPEN | AMBIGUOUS",
  "stakes_class": "LOW | STANDARD | HIGH",
  "effort_tier": "SHORT_CIRCUIT | STANDARD | ELEVATED",
  "modality": "DECIDE | ANALYSIS",
  "search_scope": "NONE | TARGETED | BROAD",
  "exploration_required": true/false,
  "short_circuit_allowed": true/false,
  "fatal_premise": true/false,
  "follow_up_questions": ["specific question 1", ...],
  "premise_flags": [
    {{
      "flag_id": "PFLAG-1",
      "flag_type": "INTERNAL_CONTRADICTION | UNSUPPORTED_ASSUMPTION | AMBIGUITY | IMPOSSIBLE_REQUEST | FRAMING_DEFECT",
      "severity": "INFO | WARNING | CRITICAL",
      "summary": "description of the defect",
      "routing": "REQUESTER_FIXABLE | MANAGEABLE_UNKNOWN | FRAMING_DEFECT | FATAL_PREMISE"
    }}
  ],
  "hidden_context_gaps": [
    {{
      "gap_id": "GAP-1",
      "description": "what context is missing",
      "impact_if_unresolved": "what happens if we proceed without it",
      "material": true/false
    }}
  ],
  "critical_assumptions": [
    {{
      "assumption_id": "CA-1",
      "text": "what we're assuming",
      "verifiability": "VERIFIABLE | UNVERIFIABLE | FALSE | UNKNOWN",
      "material": true/false
    }}
  ],
  "reasoning": "one paragraph explaining your assessment"
}}

## Rules
- ANSWERABLE: question is specific, has enough context, clear deliverable
- NEED_MORE: critical context missing, ambiguous, or fatal premise
- INVALID_FORM: question is malformed or nonsensical (maps to NEED_MORE outcome, NOT ERROR)
- short_circuit_allowed: ONLY true when question_class in [TRIVIAL, WELL_ESTABLISHED] AND stakes_class = LOW AND no CRITICAL premise flags AND no material hidden_context_gaps
- effort_tier = ELEVATED when: stakes_class = HIGH OR question_class = AMBIGUOUS OR any CRITICAL premise flag
- Surface 3-5 critical unstated assumptions. If any is UNVERIFIABLE or FALSE and material, answerability should be NEED_MORE
- ANALYSIS modality: when the question asks for exploration/mapping rather than a verdict
- DECIDE modality: when the question asks for a recommendation/assessment/verdict"""


@pipeline_stage(
    name="PreflightAssessment",
    description="Merged Gate 1 + CS Audit. Single Sonnet call. Handles admission, modality, effort, defect routing, assumptions, search scope.",
    stage_type="gate",
    order=1,
    provider="sonnet",
    inputs=["brief"],
    outputs=["PreflightResult"],
    logic="Parse JSON. ANSWERABLE->admit. NEED_MORE->reject with questions. INVALID_FORM->NEED_MORE. Parse fail->BrainError.",
    failure_mode="LLM failure or parse failure: BrainError (zero tolerance).",
    cost="1 Sonnet call",
    stage_id="preflight",
)
async def run_preflight(client, brief: str) -> PreflightResult:
    """Run the PreflightAssessment stage.

    Returns PreflightResult on success.
    Raises BrainError on LLM failure or parse failure.
    """
    prompt = PREFLIGHT_PROMPT.format(brief=brief)
    resp = await client.call("sonnet", prompt)

    if not resp.ok:
        raise BrainError("preflight", f"PreflightAssessment LLM call failed: {resp.error}")

    # Parse JSON response
    text = resp.text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        text = "\n".join(text.split("\n")[1:])
    if text.endswith("```"):
        text = "\n".join(text.split("\n")[:-1])
    text = text.strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise BrainError("preflight", f"Failed to parse PreflightAssessment JSON: {e}",
                         detail=resp.text[:500])

    # Validate required fields
    required = ["answerability", "question_class", "stakes_class", "effort_tier", "modality"]
    for field in required:
        if field not in data:
            raise BrainError("preflight", f"Missing required field: {field}",
                             detail=f"Got keys: {list(data.keys())}")

    # Build result
    try:
        premise_flags = []
        for pf in data.get("premise_flags", []):
            premise_flags.append(PremiseFlag(
                flag_id=pf.get("flag_id", "PFLAG-?"),
                flag_type=PremiseFlagType(pf.get("flag_type", "FRAMING_DEFECT")),
                severity=PremiseFlagSeverity(pf.get("severity", "WARNING")),
                summary=pf.get("summary", ""),
                routing=PremiseFlagRouting(pf.get("routing", "MANAGEABLE_UNKNOWN")),
                blocking=pf.get("severity") == "CRITICAL",
            ))

        hidden_gaps = []
        for g in data.get("hidden_context_gaps", []):
            hidden_gaps.append(HiddenContextGap(
                gap_id=g.get("gap_id", "GAP-?"),
                description=g.get("description", ""),
                impact_if_unresolved=g.get("impact_if_unresolved", ""),
                material=g.get("material", False),
            ))

        assumptions = []
        for a in data.get("critical_assumptions", []):
            assumptions.append(CriticalAssumption(
                assumption_id=a.get("assumption_id", "CA-?"),
                text=a.get("text", ""),
                verifiability=AssumptionVerifiability(a.get("verifiability", "UNKNOWN")),
                material=a.get("material", True),
            ))

        result = PreflightResult(
            executed=True,
            parse_ok=True,
            answerability=Answerability(data["answerability"]),
            question_class=QuestionClass(data["question_class"]),
            stakes_class=StakesClass(data["stakes_class"]),
            effort_tier=EffortTier(data["effort_tier"]),
            modality=Modality(data["modality"]),
            search_scope=SearchScope(data.get("search_scope", "TARGETED")),
            exploration_required=data.get("exploration_required", False),
            short_circuit_allowed=data.get("short_circuit_allowed", False),
            fatal_premise=data.get("fatal_premise", False),
            follow_up_questions=data.get("follow_up_questions", []),
            premise_flags=premise_flags,
            hidden_context_gaps=hidden_gaps,
            critical_assumptions=assumptions,
            reasoning=data.get("reasoning", ""),
        )

    except (ValueError, KeyError) as e:
        raise BrainError("preflight", f"Invalid enum value in PreflightAssessment: {e}",
                         detail=resp.text[:500])

    # Enforce admission guards (DoD v3.0 Section 4.4)
    if result.short_circuit_allowed:
        if result.question_class not in (QuestionClass.TRIVIAL, QuestionClass.WELL_ESTABLISHED):
            result.short_circuit_allowed = False
        if result.stakes_class != StakesClass.LOW:
            result.short_circuit_allowed = False
        if result.has_critical_flags:
            result.short_circuit_allowed = False
        if result.has_material_unresolved_gaps:
            result.short_circuit_allowed = False

    # Enforce elevated effort
    if (result.stakes_class == StakesClass.HIGH
            or result.question_class == QuestionClass.AMBIGUOUS
            or result.has_critical_flags):
        if result.effort_tier != EffortTier.ELEVATED:
            result.effort_tier = EffortTier.ELEVATED

    return result
