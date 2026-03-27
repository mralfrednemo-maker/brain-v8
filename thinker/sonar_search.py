"""Sonar Pro deep search for repeat topics.

V8 spec Section 6: Sonar Pro via OpenRouter for repeat searches. ~$0.01/query.
"""
from __future__ import annotations

import httpx

from thinker.types import SearchResult


async def sonar_search(query: str, api_key: str) -> list[SearchResult]:
    """Search via Sonar Pro (Perplexity) through OpenRouter."""
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
                    "messages": [{"role": "user", "content": query}],
                    "max_tokens": 4096,
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
            return [SearchResult(url="sonar-pro", title=query, snippet=text, full_content=text)]
        except Exception:
            return []
