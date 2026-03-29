"""LLM-based evidence extraction from fetched page content.

V8-F5 (Spec Section 6): After fetching full page content, one Sonnet call
per page extracts specific facts, numbers, dates, and regulatory references.
Output: structured fact items for the evidence ledger.
"""
from __future__ import annotations

import re

EXTRACTION_PROMPT = """Extract specific, verifiable facts from this web page content.

URL: {url}
Content:
{content}

Extract ONLY concrete facts — specific numbers, dates, percentages, versions,
regulatory references, statistics, named entities. Skip opinions, commentary,
and vague claims.

Format each fact as:
FACT-N: [the specific fact]

If the content has no extractable facts, respond with: NONE"""


def parse_extracted_facts(text: str) -> list[dict]:
    """Parse extracted facts from Sonnet's response.

    Returns list of {"fact": str} dicts.
    """
    if not text or text.strip().upper() == "NONE":
        return []

    facts = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue

        # Try FACT-N: format (handles bold markdown like **FACT-1:**)
        match = re.match(r"[*]*FACT-?\d+[*]*:?[*]*\s+(.+)", line)
        if match:
            facts.append({"fact": match.group(1).strip()})
            continue

        # Try numbered format: 1. fact text
        match = re.match(r"^\d+[.)]\s+(.+)", line)
        if match:
            facts.append({"fact": match.group(1).strip()})
            continue

        # Try bullet format: - FACT-N: text
        match = re.match(r"^[-*]\s+(?:FACT-?\d+:?\s+)?(.+)", line)
        if match:
            fact_text = match.group(1).strip()
            if len(fact_text) > 10:  # Skip very short fragments
                facts.append({"fact": fact_text})

    return facts


async def extract_evidence_from_page(
    llm_client, url: str, content: str, max_content: int = 30_000,
) -> list[dict]:
    """Extract structured facts from a page's content using Sonnet.

    Returns list of {"fact": str} dicts.
    Raises BrainError if the LLM call fails.
    """
    from thinker.types import BrainError

    if not content:
        return []

    truncated = content[:max_content]
    prompt = EXTRACTION_PROMPT.format(url=url, content=truncated)
    resp = await llm_client.call("sonnet", prompt)

    if not resp.ok:
        raise BrainError(
            "evidence_extraction",
            f"Evidence extraction failed for {url[:60]}: {resp.error}",
            detail="Sonnet could not extract facts from fetched page content.",
        )

    return parse_extracted_facts(resp.text)
