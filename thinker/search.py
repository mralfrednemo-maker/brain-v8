"""Search orchestration: reactive + proactive queries, topic tracking, fact extraction.

V8 spec Section 4, Search Phase:
- Reactive: Each model asked what they want looked up
- Proactive: LLM scans outputs for verifiable claims
- Dedup all queries
- Execute via Playwright (primary) or Sonar (repeat topic) or Brave (fallback)
- LLM extracts facts from full pages
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Callable, Awaitable, Optional

from thinker.types import Confidence, EvidenceItem, SearchResult


class SearchPhase(Enum):
    R1_R2 = "R1-R2"
    R2_R3 = "R2-R3"
    R3_R4 = "R3-R4"


REACTIVE_PROMPT = """A web search WILL be performed. What specific questions would you want answered with the most current data?

Your training data may be outdated on recent events, CVEs, regulatory changes, market data, and personnel changes.

Here are the model outputs from this round:
{outputs}

List 3-5 specific, searchable queries. Format:
QUERIES:
1. [query]
2. [query]
..."""

PROACTIVE_PROMPT = """Scan these model outputs for verifiable claims — specific numbers, dates, versions, events, statistics, or regulatory references that should be fact-checked.

Model outputs:
{outputs}

For each verifiable claim, generate a search query to verify it. Format:
CLAIMS:
1. '[claim]' — [why it needs verification]
2. '[claim]' — [why it needs verification]
QUERIES:
1. [search query to verify]
..."""

FACT_EXTRACTION_PROMPT = """Extract specific, relevant facts from this web page that help answer the search query.

Query: {query}
URL: {url}

Page content:
{content}

Extract atomic facts (one fact per line). Rate confidence as HIGH (authoritative primary source), MEDIUM (reputable secondary), or LOW (uncertain/opinion). Format:
FACTS:
- {{E___}} [HIGH|MEDIUM|LOW] [fact statement]
..."""


class SearchOrchestrator:
    """Orchestrates all search activities between rounds."""

    def __init__(
        self,
        llm_client,
        search_fn: Callable[..., Awaitable[list[SearchResult]]],
        sonar_fn: Optional[Callable[..., Awaitable[list[SearchResult]]]] = None,
    ):
        self._llm = llm_client
        self._search = search_fn
        self._sonar = sonar_fn
        self._searched_topics: set[str] = set()
        self._evidence_counter = 0

    def mark_topic_searched(self, topic: str):
        self._searched_topics.add(topic.lower().strip())

    def _is_repeat_topic(self, query: str) -> bool:
        query_lower = query.lower().strip()
        for topic in self._searched_topics:
            topic_words = set(topic.split())
            query_words = set(query_lower.split())
            if len(topic_words & query_words) >= max(1, len(topic_words) // 2):
                return True
        return False

    async def generate_reactive_queries(self, model_outputs: dict[str, str]) -> list[str]:
        combined = "\n\n".join(f"### {m}\n{t}" for m, t in model_outputs.items())
        resp = await self._llm.call("sonnet", REACTIVE_PROMPT.format(outputs=combined))
        if not resp.ok:
            return []
        return self._parse_queries(resp.text)

    async def generate_proactive_queries(self, model_outputs: dict[str, str]) -> list[str]:
        combined = "\n\n".join(f"### {m}\n{t}" for m, t in model_outputs.items())
        resp = await self._llm.call("sonnet", PROACTIVE_PROMPT.format(outputs=combined))
        if not resp.ok:
            return []
        return self._parse_queries(resp.text)

    def deduplicate(self, queries: list[str]) -> list[str]:
        seen: set[str] = set()
        deduped: list[str] = []
        for q in queries:
            normalized = " ".join(q.lower().split())
            if normalized not in seen:
                seen.add(normalized)
                deduped.append(q)
        return deduped

    async def execute_query(
        self, query: str, phase: SearchPhase,
    ) -> list[SearchResult]:
        if self._is_repeat_topic(query) and self._sonar:
            results = await self._sonar(query)
        else:
            results = await self._search(query)
        self.mark_topic_searched(query)
        return results

    async def extract_facts(
        self, page_content: str, url: str, query: str,
    ) -> list[EvidenceItem]:
        resp = await self._llm.call(
            "sonnet",
            FACT_EXTRACTION_PROMPT.format(
                query=query, url=url, content=page_content[:30_000],
            ),
        )
        if not resp.ok:
            return []
        return self._parse_facts(resp.text, url)

    def _parse_queries(self, text: str) -> list[str]:
        queries = []
        for line in text.split("\n"):
            line = line.strip()
            match = re.match(r"^\d+\.\s+(.+)", line)
            if match:
                queries.append(match.group(1).strip())
        return queries

    def _parse_facts(self, text: str, url: str) -> list[EvidenceItem]:
        facts = []
        for line in text.split("\n"):
            line = line.strip()
            if not line.startswith("- {"):
                continue
            match = re.match(
                r"- \{(E\d+)\}\s+\[(HIGH|MEDIUM|LOW)\]\s+(.+)", line,
            )
            if match:
                self._evidence_counter += 1
                eid = f"E{self._evidence_counter:03d}"
                conf_str = match.group(2)
                conf = Confidence[conf_str]
                facts.append(EvidenceItem(
                    evidence_id=eid,
                    topic=line[:50],
                    fact=match.group(3).strip(),
                    url=url,
                    confidence=conf,
                ))
        return facts
