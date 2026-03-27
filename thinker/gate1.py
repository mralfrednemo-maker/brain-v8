"""Gate 1: Is the question answerable?

V8 spec Section 4, Gate 1:
One fast Sonnet call reads the brief. If the question is too vague or missing
key facts: push back with specific questions. Never guess. Never search for
missing context. The requester knows their situation — ask them.

Cost: ~$0.01. Saves ~$2 and 15 minutes on garbage questions.
"""
from __future__ import annotations

import re

from thinker.pipeline import pipeline_stage
from thinker.types import Gate1Result, Outcome

GATE1_PROMPT = """You are a question quality assessor for a multi-model deliberation system.

Read the following brief and determine whether it provides enough context for 4 AI models to reason about independently and produce a useful answer.

A brief PASSES if:
- The question is specific enough that a smart human would start working on it
- Key facts are provided (who, what, when, scope)
- The question has a clear deliverable (assess, determine, evaluate, compare)

A brief NEEDS MORE if:
- Critical context is missing (no system named, no timeline, no scope)
- The question is so vague that models would have to guess
- Key terms are ambiguous without clarification

IMPORTANT: You are NOT searching for information. You are NOT filling in blanks.
You are ONLY assessing whether the brief is complete enough to reason about.

Brief:
{brief}

Respond in this exact format:
VERDICT: PASS | NEED_MORE
QUESTIONS:
- (list specific questions if NEED_MORE, leave blank if PASS)
REASONING: (one paragraph)"""


def parse_gate1_response(text: str) -> Gate1Result:
    """Parse Sonnet's Gate 1 response into a structured result."""
    # Extract verdict
    verdict_match = re.search(r"VERDICT:\s*(PASS|NEED_MORE)", text, re.IGNORECASE)
    if not verdict_match:
        # Unparseable → fail open (pass the brief through)
        return Gate1Result(passed=True, outcome=Outcome.DECIDE,
                          reasoning="Gate 1 response unparseable — passing through")

    verdict = verdict_match.group(1).upper()
    passed = verdict == "PASS"
    outcome = Outcome.DECIDE if passed else Outcome.NEED_MORE

    # Extract questions
    questions = []
    questions_match = re.search(r"QUESTIONS:\s*\n((?:- .+\n?)*)", text)
    if questions_match:
        for line in questions_match.group(1).strip().split("\n"):
            line = line.strip()
            if line.startswith("- "):
                questions.append(line[2:].strip())

    # Extract reasoning
    reasoning = ""
    reasoning_match = re.search(r"REASONING:\s*(.+)", text, re.DOTALL)
    if reasoning_match:
        reasoning = reasoning_match.group(1).strip()

    return Gate1Result(passed=passed, outcome=outcome, questions=questions, reasoning=reasoning)


@pipeline_stage(
    name="Gate 1",
    description="One fast Sonnet call checks if the brief has enough context for 4 models to reason independently. If not, pushes back with specific questions. Never guesses, never searches.",
    stage_type="gate",
    provider="sonnet",
    inputs=["brief"],
    outputs=["passed (bool)", "questions (list)", "reasoning (str)"],
    prompt=GATE1_PROMPT,
    logic="""PASS if: question specific, key facts provided (who/what/when/scope), clear deliverable.
NEED_MORE if: critical context missing, too vague, ambiguous terms.
MALFORMED response: fail open (PASS).
LLM failure: fail open (PASS).""",
    failure_mode="Fail open — don't block the pipeline on infra issues",
    cost="~$0.01 per call (Anthropic Max subscription = $0)",
    stage_id="gate1",
)
async def run_gate1(client, brief: str) -> Gate1Result:
    """Run Gate 1 assessment.

    Args:
        client: LLM client (real or mock) with async call(model, prompt) method.
        brief: The full brief text.

    Returns:
        Gate1Result with pass/fail, outcome, and any push-back questions.
    """
    resp = await client.call("sonnet", GATE1_PROMPT.format(brief=brief))

    if not resp.ok:
        # LLM failure → fail open (don't block on infra issues)
        return Gate1Result(
            passed=True, outcome=Outcome.DECIDE,
            reasoning=f"Gate 1 LLM failed ({resp.error}) — passing through",
        )

    return parse_gate1_response(resp.text)
