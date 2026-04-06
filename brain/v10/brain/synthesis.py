"""Synthesis Gate — generates the final deliberation report.

Not an agent — a single LLM call that synthesizes the final round's views
into a dual-format output: JSON (machine-readable) + markdown (human-readable).

The deterministic classification label (CONSENSUS, CLOSED_WITH_ACCEPTED_RISKS, etc.)
is appended to the output after the LLM call.
"""
from __future__ import annotations

from brain.pipeline import pipeline_stage

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
}}

---DISPOSITIONS---

SECTION 3: Structured dispositions (one per line)
For EVERY open finding listed in the Curated State Bundle (open blockers, active/contested frames,
decisive claims, unresolved contradictions), emit a disposition line:

DISPOSITION: [BLOCKER|FRAME|CLAIM|CONTRADICTION] | [target_id] | [RESOLVED|DEFERRED|ACCEPTED_RISK|MITIGATED] | [LOW|MEDIUM|HIGH|CRITICAL] | [one-sentence explanation]

If you cannot address a finding, still emit DISPOSITION with status DEFERRED and explain why.
Omitting dispositions for open findings is a compliance failure."""


def build_synthesis_prompt(
    brief: str,
    final_views: dict[str, str],
    blocker_summary: dict,
    evidence_text: str = "",
    synthesis_packet_text: str = "",
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
    if synthesis_packet_text:
        prompt += f"\n\n{synthesis_packet_text}\n"
    return prompt


def parse_synthesis_output(text: str) -> tuple[str, dict, list[dict]]:
    """Split synthesis output into markdown report, JSON object, and dispositions.

    Returns (markdown_report, json_data, dispositions).
    """
    import json

    dispositions = []

    # Extract dispositions section first
    if "---DISPOSITIONS---" in text:
        parts = text.split("---DISPOSITIONS---", 1)
        text = parts[0]
        disp_text = parts[1].strip()
        # Also split off JSON if it appears after dispositions
        if "---JSON---" in disp_text:
            disp_text, extra = disp_text.split("---JSON---", 1)
            text = text + "---JSON---" + extra
        for line in disp_text.split("\n"):
            line = line.strip()
            if line.startswith("DISPOSITION:"):
                parts_d = [p.strip() for p in line[len("DISPOSITION:"):].split("|")]
                if len(parts_d) >= 5:
                    dispositions.append({
                        "target_type": parts_d[0],
                        "target_id": parts_d[1],
                        "status": parts_d[2],
                        "importance": parts_d[3],
                        "narrative_explanation": parts_d[4],
                    })

    if "---JSON---" in text:
        parts = text.split("---JSON---", 1)
        markdown = parts[0].strip()
        json_text = parts[1].strip()
    else:
        markdown = text.strip()
        json_text = ""

    json_data = {}
    if json_text:
        json_text = json_text.strip()
        if json_text.startswith("```"):
            json_text = "\n".join(json_text.split("\n")[1:])
        if json_text.endswith("```"):
            json_text = "\n".join(json_text.split("\n")[:-1])
        try:
            json_data = json.loads(json_text.strip())
        except json.JSONDecodeError:
            json_data = {"parse_error": "Failed to parse JSON section", "raw": json_text[:500]}

    return markdown, json_data, dispositions


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
    synthesis_packet_text: str = "",
) -> tuple[str, dict, list[dict]]:
    """Run the Synthesis Gate. Returns (markdown_report, json_data, dispositions).

    The outcome_class is appended to both outputs after the LLM call.
    V9: Accepts curated synthesis packet text + returns structured dispositions.
    """
    prompt = build_synthesis_prompt(
        brief, final_views, blocker_summary,
        evidence_text=evidence_text,
        synthesis_packet_text=synthesis_packet_text,
    )
    resp = await client.call("sonnet", prompt)

    if not resp.ok:
        from brain.types import BrainError
        raise BrainError("synthesis", f"Synthesis gate LLM call failed: {resp.error}",
                         detail="Cannot produce deliberation report without a working Sonnet call.")

    markdown, json_data, dispositions = parse_synthesis_output(resp.text)

    # Append deterministic classification
    if outcome_class:
        markdown += f"\n\n---\n**Classification: {outcome_class}**\n"
        json_data["outcome_class"] = outcome_class

    return markdown, json_data, dispositions
