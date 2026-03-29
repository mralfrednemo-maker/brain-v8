"""Full page content fetch — retrieves and strips HTML from search result URLs.

V8-F4 (Spec Section 6): After search returns URLs, fetch top N pages via httpx.
Extract page text (strip HTML tags). Truncate to max_chars.
Store in SearchResult.full_content.

Also fixes V8-B1: Bing returns URLs without titles/snippets — fetching
the page provides the actual content.
"""
from __future__ import annotations

import re
from html import unescape

import httpx

from thinker.types import SearchResult


def strip_html(html: str) -> str:
    """Strip HTML tags, scripts, styles, and decode entities.

    Returns clean text suitable for evidence extraction.
    """
    # Remove script and style blocks
    text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)
    # Decode HTML entities
    text = unescape(text)
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def truncate_content(text: str, max_chars: int = 50_000) -> str:
    """Truncate text to max_chars."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars]


async def fetch_page_content(
    url: str, timeout: float = 15.0, max_chars: int = 50_000,
) -> str:
    """Fetch a URL and return stripped, truncated text content.

    Returns empty string on any error (timeout, HTTP error, etc.).
    Does not raise — errors are expected for some URLs.
    """
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=timeout,
        headers={"User-Agent": "Mozilla/5.0 (compatible; ThinkerV8/1.0)"},
    ) as client:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            html = resp.text
            text = strip_html(html)
            return truncate_content(text, max_chars)
        except Exception:
            return ""


async def fetch_pages_for_results(
    results: list[SearchResult], max_pages: int = 5, max_chars: int = 50_000,
) -> None:
    """Fetch full page content for the top N search results in-place.

    Populates SearchResult.full_content for each result.
    Skips results that already have full_content.
    """
    for sr in results[:max_pages]:
        if sr.full_content:
            continue
        content = await fetch_page_content(sr.url, max_chars=max_chars)
        if content:
            sr.full_content = content
            # Also fill in title if missing (B1 fix for Bing)
            if not sr.title:
                # Use first sentence as title approximation
                sr.title = content[:100].split('.')[0].strip()[:200]
