"""Gate 1: Is the question answerable?

V8 spec Section 4, Gate 1:
One fast Sonnet call reads the brief. If the question is too vague or missing
key facts: push back with specific questions. Never guess. Never search for
missing context. The requester knows their situation — ask them.

Cost: ~$0.01. Saves ~$2 and 15 minutes on garbage questions.
"""
from __future__ import annotations

import re

from brain.pipeline import pipeline_stage
from brain.types import Gate1Result, Outcome

GATE1_PROMPT = """You are a question quality assessor for a multi-model deliberation system.

Read the following brief and determine:
1. Whether it provides enough context for 4 AI models to reason about independently
2. Whether web search would improve the deliberation quality

A brief PASSES if:
- The question is specific enough that a smart human would start working on it
- Key facts are provided (who, what, when, scope)
- The question has a clear deliverable (assess, determine, evaluate, compare)

A brief NEEDS MORE if:
- Critical context is missing (no system named, no timeline, no scope)
- The question is so vague that models would have to guess
- Key terms are ambiguous without clarification

SEARCH is YES if the brief contains:
- Specific regulatory/legal references that should be verified (GDPR articles, CFR sections, etc.)
- Numeric claims, statistics, or benchmarks that could be fact-checked
- References to specific products, versions, CVEs, or standards
- Questions where current/recent information matters

SEARCH is NO if:
- The brief is a pure reasoning/logic/strategy question with no factual claims to verify
- All necessary facts are already provided in the brief
- The question is about internal architecture or design choices, not external facts

IMPORTANT: You are NOT searching for information. You are NOT filling in blanks.
You are ONLY assessing the brief and recommending whether search would help.

Brief:
{brief}

Respond in this exact format:
VERDICT: PASS | NEED_MORE
SEARCH: YES | NO
SEARCH_REASONING: (one sentence explaining why search is or isn't needed)
QUESTIONS:
- (list specific questions if NEED_MORE, leave blank if PASS)
REASONING: (one paragraph on the verdict)"""


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

    # Extract search recommendation (default YES if missing — conservative)
    search_match = re.search(r"SEARCH:\s*(YES|NO)", text, re.IGNORECASE)
    search_recommended = True  # Default: search
    if search_match:
        search_recommended = search_match.group(1).upper() == "YES"

    # Extract search reasoning
    search_reasoning = ""
    sr_match = re.search(r"SEARCH_REASONING:\s*(.+?)(?:\n|$)", text)
    if sr_match:
        search_reasoning = sr_match.group(1).strip()

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

    return Gate1Result(passed=passed, outcome=outcome, questions=questions,
                       reasoning=reasoning, search_recommended=search_recommended,
                       search_reasoning=search_reasoning)


@pipeline_stage(
    name="Gate 1",
    description="One fast Sonnet call checks if the brief has enough context for 4 models to reason independently. If not, pushes back with specific questions. Never guesses, never searches.",
    stage_type="gate",
    order=1,
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
        from brain.types import BrainError
        raise BrainError("gate1", f"Sonnet LLM call failed: {resp.error}",
                         detail="Gate 1 cannot assess brief quality without a working LLM.")

    return parse_gate1_response(resp.text)
