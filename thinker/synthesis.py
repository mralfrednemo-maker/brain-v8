"""Synthesis Gate — generates the final deliberation report.

Not an agent — a single LLM call that synthesizes the final round's views
into a dual-format output: JSON (machine-readable) + markdown (human-readable).

The deterministic classification label (CONSENSUS, CLOSED_WITH_ACCEPTED_RISKS, etc.)
is appended to the output after the LLM call.
"""
from __future__ import annotations

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
) -> str:
    views_text = "\n\n".join(f"### {m}\n{v}" for m, v in final_views.items())
    blocker_text = "\n".join(f"- {k}: {v}" for k, v in blocker_summary.items()) if blocker_summary else "None"
    return SYNTHESIS_PROMPT.format(
        brief=brief, views=views_text, blocker_summary=blocker_text,
    )


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


async def run_synthesis(
    client,
    brief: str,
    final_views: dict[str, str],
    blocker_summary: dict,
    outcome_class: str = "",
) -> tuple[str, dict]:
    """Run the Synthesis Gate. Returns (markdown_report, json_data).

    The outcome_class is appended to both outputs after the LLM call.
    """
    prompt = build_synthesis_prompt(brief, final_views, blocker_summary)
    resp = await client.call("sonnet", prompt)

    if not resp.ok:
        markdown = (
            f"# Synthesis Failed\n\nSynthesis gate failed: {resp.error}\n"
        )
        json_data = {"status": "FAILED", "error": resp.error}
        return markdown, json_data

    markdown, json_data = parse_synthesis_output(resp.text)

    # Append deterministic classification
    if outcome_class:
        markdown += f"\n\n---\n**Classification: {outcome_class}**\n"
        json_data["outcome_class"] = outcome_class

    return markdown, json_data
