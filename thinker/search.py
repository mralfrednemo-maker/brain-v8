"""Search orchestration: model-requested + proactive queries, topic tracking.

Search flow:
1. Parse model search requests from their output appendices (direct, no guessing)
2. Sonnet proactive sweep for claims models didn't ask about
3. Deduplicate all queries
4. Execute via Playwright (primary) or Sonar (repeat topic) or Brave (fallback)
5. Keep top 10 results in Google ranking order (trust Google's authority ranking)
6. Search after R1 and R2 only (not R3)
7. Topic tracker persists across rounds — repeat topic triggers Sonar
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Callable, Awaitable, Optional

from thinker.pipeline import pipeline_stage
from thinker.types import Confidence, EvidenceItem, SearchResult


class SearchPhase(Enum):
    R1_R2 = "R1-R2"
    R2_R3 = "R2-R3"


PROACTIVE_PROMPT = """Scan these model outputs for verifiable claims that the models did NOT request to be searched.
Look for specific numbers, dates, versions, events, statistics, or regulatory references that should be fact-checked.

Model outputs:
{outputs}

Model-requested searches (ALREADY QUEUED — do not duplicate):
{already_queued}

Generate search queries ONLY for claims the models missed. If the models already covered everything, return NONE.

Format:
QUERIES:
1. [search query]
2. ...
(or NONE if nothing additional needed)"""


def parse_model_search_requests(model_output: str) -> list[str]:
    """Parse search requests from a model's output appendix.

    Models append a SEARCH_REQUESTS section with 0-5 queries.
    """
    queries = []
    in_section = False
    for line in model_output.split("\n"):
        line = line.strip()
        if "SEARCH_REQUESTS:" in line or "SEARCH REQUESTS:" in line:
            in_section = True
            continue
        if in_section:
            if line.upper() == "NONE" or line == "":
                break
            match = re.match(r"^\d+\.\s+(.+)", line)
            if match:
                queries.append(match.group(1).strip())
            elif line.startswith("- "):
                queries.append(line[2:].strip())
            else:
                if queries:
                    break
    # Strip surrounding quotes — models often wrap queries in "..." which
    # causes exact-match search returning 0 results
    return [q.strip('"\'') for q in queries[:5]]


class SearchOrchestrator:
    """Orchestrates all search activities between rounds."""

    def __init__(
        self,
        llm_client,
        search_fn: Callable[..., Awaitable[list[SearchResult]]],
        sonar_fn: Optional[Callable[..., Awaitable[list[SearchResult]]]] = None,
        max_results: int = 10,
    ):
        self._llm = llm_client
        self._search = search_fn
        self._sonar = sonar_fn
        self._searched_topics: set[str] = set()
        self._max_results = max_results

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

    def collect_model_requests(self, model_outputs: dict[str, str]) -> list[str]:
        """Parse search requests directly from model output appendices."""
        all_queries = []
        for model, output in model_outputs.items():
            queries = parse_model_search_requests(output)
            all_queries.extend(queries)
        return all_queries

    async def generate_proactive_queries(
        self, model_outputs: dict[str, str], already_queued: list[str],
    ) -> list[str]:
        """Sonnet sweep for claims models didn't ask to be searched."""
        combined = "\n\n".join(f"### {m}\n{t}" for m, t in model_outputs.items())
        queued_text = "\n".join(f"- {q}" for q in already_queued) if already_queued else "NONE"
        resp = await self._llm.call(
            "sonnet",
            PROACTIVE_PROMPT.format(outputs=combined, already_queued=queued_text),
        )
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
        """Execute a single search query. Results in ranking order (top 10)."""
        query = query.strip('"\'')  # Strip quotes that cause exact-match failures
        if self._is_repeat_topic(query) and self._sonar:
            results = await self._sonar(query)
        else:
            results = await self._search(query)
        self.mark_topic_searched(query)
        return results[:self._max_results]

    def _parse_queries(self, text: str) -> list[str]:
        for line in text.split("\n"):
            line = line.strip()
            if line.upper() == "NONE":
                return []
            if line:
                break
        queries = []
        for line in text.split("\n"):
            line = line.strip()
            match = re.match(r"^\d+\.\s+(.+)", line)
            if match:
                queries.append(match.group(1).strip())
        return queries


@pipeline_stage(
    name="Search Phase",
    description="Runs after R1 and R2 only. Collects model-requested searches from appendices (0-5 per model, no LLM needed). Sonnet proactive sweep for claims models missed. Dedup. Execute via Brave (primary) or Sonar (repeat topic). Top 10 results in search ranking order. Trust search engine ranking — no re-ranking.",
    stage_type="search",
    order=5,
    provider="brave ($0.01/query) + sonar (repeat topics) + sonnet (proactive sweep)",
    inputs=["model_outputs", "topic_tracker_state"],
    outputs=["evidence_items (added to ledger)", "queries_executed (int)"],
    prompt=PROACTIVE_PROMPT,
    logic="""1. Parse SEARCH_REQUESTS from model output appendices (direct, no LLM).
2. Sonnet proactive sweep for uncovered claims (1 LLM call).
3. Deduplicate (case-insensitive).
4. First-time topic → Brave. Repeat topic → Sonar Pro.
5. Results kept in search ranking order. Max 10 items in evidence ledger.""",
    failure_mode="Search fails: empty results, deliberation continues without evidence.",
    cost="~$0.05 per search phase (Brave) + 1 Sonnet call ($0)",
    stage_id="search",
)
def _register_search(): pass
