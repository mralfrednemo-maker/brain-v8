"""Sonar Pro deep search for repeat topics.

V8 spec Section 6: When the topic tracker detects a repeat topic (same subject
searched twice across rounds), Sonar Pro is used instead of Brave for deeper results.
Sonar Pro returns synthesized answers with source citations.
"""
from __future__ import annotations

import httpx

from brain.types import SearchResult


async def sonar_search(query: str, api_key: str, max_results: int = 10) -> list[SearchResult]:
    """Search via Sonar Pro (Perplexity) through OpenRouter.

    Returns SearchResult items with citations extracted from Sonar's response.
    """
    from brain.brave_search import SearchError

    if not api_key:
        raise SearchError("Sonar search: no OpenRouter API key configured")

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "perplexity/sonar-pro",
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are a research assistant. Answer the query with specific, "
                                "verifiable facts. Include source URLs for each fact. Be concise."
                            ),
                        },
                        {"role": "user", "content": query},
                    ],
                    "max_tokens": 4096,
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

            # Guard against malformed API responses
            try:
                text = data["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError) as e:
                raise SearchError(f"Sonar returned unexpected response structure: {e}")

            citations = data.get("citations", [])

            results = []
            if citations:
                for i, url in enumerate(citations[:max_results]):
                    url_str = url if isinstance(url, str) else url.get("url", "")
                    results.append(SearchResult(
                        url=url_str,
                        title=f"Sonar: {query[:60]}",
                        snippet="",
                        full_content=text if i == 0 else "",
                    ))
            else:
                results.append(SearchResult(
                    url="sonar-pro-synthesis",
                    title=f"Sonar Pro: {query[:80]}",
                    snippet=text[:300],
                    full_content=text,
                ))

            return results[:max_results]
        except httpx.TimeoutException:
            raise SearchError(f"Sonar search timed out: {query[:60]}")
        except httpx.HTTPStatusError as e:
            raise SearchError(f"Sonar search HTTP {e.response.status_code}: {query[:60]}")
        except Exception as e:
            raise SearchError(f"Sonar search failed: {e}")
