"""Synthesis Gate — generates the final deliberation report.

Not an agent — a single LLM call that synthesizes the final round's views
into a dual-format output: JSON (machine-readable) + markdown (human-readable).

The deterministic classification label (CONSENSUS, CLOSED_WITH_ACCEPTED_RISKS, etc.)
is appended to the output after the LLM call.
"""
from __future__ import annotations

from thinker.pipeline import pipeline_stage

SYNTHESIS_PROMPT = """You are the synthesis gate for a multi-model deliberation system.

Your job is to write a clear, honest report summarizing what the models concluded.

## Rules
1. You may ONLY summarize and synthesize the views below. DO NOT INVENT NEW ARGUMENTS.
2. If models disagreed, state the disagreement clearly — do not paper over it.
3. If evidence is weak, say so. Do not inflate confidence.
4. Use evidence IDs (E001-E999) when referencing specific facts.

## Brief
{brief}

## Final Round Views (these are the ONLY inputs you may use)
{views}

## Blocker Summary
{blocker_summary}

## Output Format

You MUST produce TWO sections separated by a line containing only "---JSON---".

SECTION 1: Markdown report
# Deliberation Report: [Title]

## TL;DR
[2-3 sentence executive summary]

## Verdict
[Position + confidence + consensus level]

## Consensus Map
### Agreed
[Points all models agreed on]
### Contested
[Points where models diverged — state both sides honestly]

## Key Findings
[Numbered, with evidence citations where available]

## Risk Factors
[Table: Risk | Severity | Mitigation]

---JSON---

SECTION 2: JSON object (fill fields if applicable, use "N/A" if not)
{{
  "title": "...",
  "tldr": "...",
  "verdict": "...",
  "confidence": "high|medium|low",
  "agreed_points": ["...", "..."],
  "contested_points": ["...", "..."],
  "key_findings": ["...", "..."],
  "risk_factors": [{{"risk": "...", "severity": "...", "mitigation": "..."}}],
  "evidence_cited": ["E001", "E002"],
  "unresolved_questions": ["...", "..."]
}}"""


def build_synthesis_prompt(
    brief: str,
    final_views: dict[str, str],
    blocker_summary: dict,
    evidence_text: str = "",
) -> str:
    views_text = "\n\n".join(f"### {m}\n{v}" for m, v in final_views.items())
    blocker_text = "\n".join(f"- {k}: {v}" for k, v in blocker_summary.items()) if blocker_summary else "None"
    prompt = SYNTHESIS_PROMPT.format(
        brief=brief, views=views_text, blocker_summary=blocker_text,
    )
    if evidence_text:
        prompt += (
            "\n\n## Web-Verified Evidence (AUTHORITATIVE)\n\n"
            "The following evidence was retrieved from web sources during deliberation. "
            "Cite evidence IDs when referencing specific facts.\n\n"
            f"{evidence_text}\n"
        )
    return prompt


def parse_synthesis_output(text: str) -> tuple[str, dict]:
    """Split synthesis output into markdown report and JSON object.

    Returns (markdown_report, json_data). If JSON parsing fails,
    json_data is a dict with error info.
    """
    import json

    if "---JSON---" in text:
        parts = text.split("---JSON---", 1)
        markdown = parts[0].strip()
        json_text = parts[1].strip()
    else:
        # LLM didn't follow format — treat whole thing as markdown
        markdown = text.strip()
        json_text = ""

    json_data = {}
    if json_text:
        # Strip markdown code fences if present
        json_text = json_text.strip()
        if json_text.startswith("```"):
            json_text = "\n".join(json_text.split("\n")[1:])
        if json_text.endswith("```"):
            json_text = "\n".join(json_text.split("\n")[:-1])
        try:
            json_data = json.loads(json_text.strip())
        except json.JSONDecodeError:
            json_data = {"parse_error": "Failed to parse JSON section", "raw": json_text[:500]}

    return markdown, json_data


@pipeline_stage(
    name="Synthesis Gate",
    description="Single Sonnet call. Sees ONLY final round views. Produces dual output: markdown (human-readable) + JSON (machine-readable). DO NOT INVENT NEW ARGUMENTS. Deterministic classification label appended after LLM call.",
    stage_type="synthesis",
    order=6,
    provider="sonnet",
    inputs=["brief", "final_views (R3 only)", "blocker_summary", "outcome_class"],
    outputs=["markdown_report (str)", "json_data (dict)"],
    prompt=SYNTHESIS_PROMPT,
    logic="""Rules: ONLY summarize final views. State disagreement honestly. Cite evidence IDs.
Dual output separated by ---JSON--- line.
Classification (CONSENSUS/CLOSED_WITH_ACCEPTED_RISKS/etc.) appended deterministically.""",
    failure_mode="LLM fails: return FAILED status with error details.",
    cost="1 Sonnet call ($0 on Max subscription)",
    stage_id="synthesis",
)
async def run_synthesis(
    client,
    brief: str,
    final_views: dict[str, str],
    blocker_summary: dict,
    outcome_class: str = "",
    evidence_text: str = "",
) -> tuple[str, dict]:
    """Run the Synthesis Gate. Returns (markdown_report, json_data).

    The outcome_class is appended to both outputs after the LLM call.
    """
    prompt = build_synthesis_prompt(brief, final_views, blocker_summary, evidence_text=evidence_text)
    resp = await client.call("sonnet", prompt)

    if not resp.ok:
        from thinker.types import BrainError
        raise BrainError("synthesis", f"Synthesis gate LLM call failed: {resp.error}",
                         detail="Cannot produce deliberation report without a working Sonnet call.")

    markdown, json_data = parse_synthesis_output(resp.text)

    # Append deterministic classification
    if outcome_class:
        markdown += f"\n\n---\n**Classification: {outcome_class}**\n"
        json_data["outcome_class"] = outcome_class

    return markdown, json_data
