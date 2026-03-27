"""Hermes Synthesis — generates the final deliberation report.

V8 spec Section 4, Synthesis:
Hermes (Claude Sonnet) writes a human-readable report. Sees ONLY the final
round's views. "DO NOT INVENT NEW ARGUMENTS." Very strict.
"""
from __future__ import annotations

SYNTHESIS_PROMPT = """You are Hermes, the synthesis engine for a multi-model deliberation system.

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
Write a YAML frontmatter header followed by a markdown report:

```
---
final_status: COMPLETE | PARTIAL | INSUFFICIENT
v3_outcome_class: CONSENSUS | PARTIAL_CONSENSUS | NO_CONSENSUS
confidence: high | medium | low
---

# Deliberation Report: [Title]

## TL;DR
[2-3 sentence executive summary]

## Verdict
[Position + confidence + consensus level]

## Consensus Map
### Agreed
### Contested

## Key Findings
[Numbered, with evidence citations]

## Risk Factors
[Table: Risk | Severity | Mitigation]
```"""


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


async def run_synthesis(
    client,
    brief: str,
    final_views: dict[str, str],
    blocker_summary: dict,
) -> str:
    """Run Hermes synthesis. Returns the full markdown report."""
    prompt = build_synthesis_prompt(brief, final_views, blocker_summary)
    resp = await client.call("sonnet", prompt)

    if not resp.ok:
        return (
            "---\n"
            "final_status: DEGRADED\n"
            "v3_outcome_class: NO_CONSENSUS\n"
            "confidence: low\n"
            "---\n\n"
            f"# Synthesis Failed\n\nHermes synthesis failed: {resp.error}\n"
        )

    return resp.text
