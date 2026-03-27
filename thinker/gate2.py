"""Gate 2: Can we trust this answer?

V8 spec Section 4, Gate 2:
Gate 2 is NOT boolean checkboxes. It's LLM judgment backed by mechanical
tool data. The tools provide the DATA. The LLM provides the JUDGMENT.

Five questions:
1. Models converged? (Position Tracker data -> LLM judges reasoning agreement)
2. Evidence credible? (Contradiction Detector data -> LLM judges source quality)
3. Dissent addressed? (Argument Tracker data -> LLM judges engagement quality)
4. Enough data found? (Evidence count + gaps -> LLM judges sufficiency)
5. Report honest? (Blocker IDs in report -> LLM judges genuine engagement)
"""
from __future__ import annotations

import re

from thinker.types import (
    Argument, Blocker, Contradiction, Gate2Assessment, Outcome, Position,
)


GATE2_PROMPT = """You are the final trust gate for a multi-model deliberation system.
Your job is to determine whether the answer is trustworthy enough to act on,
or whether it should be escalated to a human decision maker.

You will receive MECHANICAL DATA from automated tools, plus the synthesis report.
The tools provide data. YOU provide judgment.

## Mechanical Data

### Convergence
agreement_ratio: {agreement_ratio}
Final positions:
{position_summary}

### Evidence
Total evidence items: {evidence_count}
Contradictions detected: {contradiction_summary}

### Dissent
Unaddressed arguments after final round: {unaddressed_summary}

### Open Blockers
{blocker_summary}

### Synthesis Report
{report_text}

## Your Assessment

For each question, answer YES or NO with a brief justification.
"YES" means the data supports trust. "NO" means it doesn't.

CONVERGENCE: YES/NO — Do models agree for the SAME REASONS? (Labels matching != reasoning agrees)
EVIDENCE: YES/NO — Are sources authoritative, current, and cross-corroborated?
DISSENT: YES/NO — Were all significant arguments substantively engaged with?
DATA: YES/NO — Given the evidence found, can the question be answered confidently?
REPORT: YES/NO — Does the report genuinely engage with each blocker, or just name-drop?

Then give your final verdict:
VERDICT: DECIDE | ESCALATE
REASONING: (one paragraph)"""


def build_gate2_prompt(
    agreement_ratio: float,
    positions: dict[str, Position],
    contradictions: list[Contradiction],
    unaddressed_arguments: list[Argument],
    open_blockers: list[Blocker],
    evidence_count: int,
    report_text: str,
) -> str:
    """Build Gate 2 prompt with all mechanical tool data injected."""
    # Position summary
    if positions:
        pos_lines = [f"  {m}: {p.primary_option} [{p.confidence.value}] {p.qualifier}"
                     for m, p in positions.items()]
        position_summary = "\n".join(pos_lines)
    else:
        position_summary = "  (no position data available)"

    # Contradiction summary
    if contradictions:
        ctr_lines = [f"  {c.contradiction_id}: {c.topic} [{c.severity}] — evidence {c.evidence_ids}"
                     for c in contradictions]
        contradiction_summary = "\n".join(ctr_lines)
    else:
        contradiction_summary = "  None detected"

    # Unaddressed arguments
    if unaddressed_arguments:
        ua_lines = [f"  {a.argument_id}: [{a.model}] {a.text} ({a.status.value})"
                    for a in unaddressed_arguments]
        unaddressed_summary = "\n".join(ua_lines)
    else:
        unaddressed_summary = "  All arguments addressed"

    # Open blockers
    if open_blockers:
        bl_lines = [f"  {b.blocker_id}: {b.kind.value} — {b.detail}" for b in open_blockers]
        blocker_summary = "\n".join(bl_lines)
    else:
        blocker_summary = "  No open blockers"

    return GATE2_PROMPT.format(
        agreement_ratio=agreement_ratio,
        position_summary=position_summary,
        evidence_count=evidence_count,
        contradiction_summary=contradiction_summary,
        unaddressed_summary=unaddressed_summary,
        blocker_summary=blocker_summary,
        report_text=report_text[:5000],
    )


def _parse_gate2_response(text: str) -> Gate2Assessment:
    """Parse Sonnet's Gate 2 assessment."""
    def _check(label: str) -> bool:
        match = re.search(rf"{label}:\s*(YES|NO)", text, re.IGNORECASE)
        return match.group(1).upper() == "YES" if match else False

    verdict_match = re.search(r"VERDICT:\s*(DECIDE|ESCALATE)", text, re.IGNORECASE)
    outcome = Outcome.DECIDE if verdict_match and verdict_match.group(1).upper() == "DECIDE" else Outcome.ESCALATE

    reasoning_match = re.search(r"REASONING:\s*(.+)", text, re.DOTALL)
    reasoning = reasoning_match.group(1).strip() if reasoning_match else ""

    return Gate2Assessment(
        outcome=outcome,
        convergence_ok=_check("CONVERGENCE"),
        evidence_credible=_check("EVIDENCE"),
        dissent_addressed=_check("DISSENT"),
        enough_data=_check("DATA"),
        report_honest=_check("REPORT"),
        reasoning=reasoning,
    )


async def run_gate2(
    client,
    agreement_ratio: float,
    positions: dict[str, Position],
    contradictions: list[Contradiction],
    unaddressed_arguments: list[Argument],
    open_blockers: list[Blocker],
    evidence_count: int,
    report_text: str,
) -> Gate2Assessment:
    """Run Gate 2 trust assessment.

    Feeds mechanical tool data to Sonnet for LLM judgment.
    On LLM failure: escalate (conservative — don't auto-decide without trust check).
    """
    prompt = build_gate2_prompt(
        agreement_ratio, positions, contradictions,
        unaddressed_arguments, open_blockers, evidence_count, report_text,
    )
    resp = await client.call("sonnet", prompt)

    if not resp.ok:
        return Gate2Assessment(
            outcome=Outcome.ESCALATE,
            convergence_ok=False, evidence_credible=False,
            dissent_addressed=False, enough_data=False, report_honest=False,
            reasoning=f"Gate 2 LLM failed ({resp.error}) — escalating conservatively",
        )

    return _parse_gate2_response(resp.text)
