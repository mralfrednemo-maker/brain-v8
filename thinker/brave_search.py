"""Brave API fallback search.

V8 spec Section 6: Brave API as fallback when Playwright fails. ~$0.01/query.
"""
from __future__ import annotations

import httpx

from thinker.types import SearchResult


async def brave_search(query: str, api_key: str, max_results: int = 10) -> list[SearchResult]:
    """Search via Brave Search API."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers={"X-Subscription-Token": api_key, "Accept": "application/json"},
                params={"q": query, "count": max_results},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            results = []
            for item in data.get("web", {}).get("results", []):
                results.append(SearchResult(
                    url=item.get("url", ""),
                    title=item.get("title", ""),
                    snippet=item.get("description", ""),
                ))
            return results
        except Exception:
            return []
