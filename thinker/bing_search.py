"""Free Bing search via curl_cffi (PRIMARY search provider, no API key needed).

Uses curl_cffi to impersonate a real browser's TLS fingerprint, bypassing
Bing's CAPTCHA detection. The scope=web&FORM=HDRSC1 parameters force
English web results regardless of IP geolocation.
"""
from __future__ import annotations

import re
from html import unescape
from urllib.parse import unquote

from thinker.types import SearchResult


def _resolve_bing_redirect(href: str) -> str:
    """Extract real URL from Bing redirect: bing.com/ck/a?...&u=a1ENCODED_URL...

    The 'u' parameter contains the real URL with 'a1' prefix, URL-encoded.
    Falls back to the raw href if extraction fails.
    """
    if "bing.com/ck/" not in href:
        return href

    # Extract u= parameter
    u_match = re.search(r'[?&]u=a1(.*?)(?:&|$)', href)
    if u_match:
        try:
            decoded = unquote(u_match.group(1))
            if decoded.startswith("http"):
                return decoded
        except Exception:
            pass

    return href


async def bing_search(query: str, max_results: int = 10) -> list[SearchResult]:
    """Search Bing via curl_cffi — free, no API key, bypasses CAPTCHA.

    Uses scope=web&FORM=HDRSC1 to force English web results regardless
    of IP geolocation (tested from EU IP, returns English results).
    """
    from thinker.brave_search import SearchError

    try:
        from curl_cffi import requests as curl_requests
    except ImportError:
        raise SearchError("Bing search requires curl_cffi: pip install curl_cffi")

    try:
        resp = curl_requests.get(
            "https://www.bing.com/search",
            params={"q": query, "scope": "web", "FORM": "HDRSC1"},
            headers={"Accept-Language": "en-US,en;q=0.9"},
            impersonate="chrome131",
            timeout=15,
        )

        html = resp.text

        # Hard block: CAPTCHA with no results behind it
        if "captcha" in html.lower() and "b_algo" not in html.lower():
            raise SearchError(f"Bing CAPTCHA block (no results) for: {query[:50]}")

        # Strategy 1: Extract from data-url attributes (most reliable on modern Bing)
        results = []
        seen_urls = set()

        data_urls = re.findall(r'data-(?:url|href)="(https?://[^"]+)"', html)
        for url in data_urls:
            url = unescape(url)
            if "bing.com" in url or "microsoft.com" in url:
                continue
            if url in seen_urls:
                continue
            seen_urls.add(url)
            results.append(SearchResult(url=url, title="", snippet=""))

        # Strategy 2: Extract from <h2><a href> blocks (classic Bing HTML)
        algos = re.findall(r'<li class="b_algo"[^>]*>(.*?)</li>', html, re.DOTALL)
        for block in algos:
            a_match = re.search(
                r'<h2[^>]*><a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', block, re.DOTALL
            )
            if not a_match:
                continue
            raw_href = unescape(a_match.group(1))
            url = _resolve_bing_redirect(raw_href)
            if "bing.com" in url or "microsoft.com" in url or url in seen_urls:
                continue
            seen_urls.add(url)
            title = re.sub(r'<[^>]+>', '', a_match.group(2)).strip()
            title = unescape(title)
            snippet_match = re.search(r'<p[^>]*>(.*?)</p>', block, re.DOTALL)
            snippet = ""
            if snippet_match:
                snippet = re.sub(r'<[^>]+>', '', snippet_match.group(1)).strip()
                snippet = unescape(snippet)
            results.append(SearchResult(url=url, title=title[:200], snippet=snippet[:500]))

        # Enrich results with titles/snippets from cite tags
        cites = re.findall(r'<cite[^>]*>(.*?)</cite>', html)
        cite_titles = re.findall(
            r'<a[^>]+(?:data-url|href)="(https?://[^"]+)"[^>]*>(.*?)</a>', html, re.DOTALL
        )
        title_map = {}
        for href, title_html in cite_titles:
            href = unescape(href)
            title = re.sub(r'<[^>]+>', '', title_html).strip()
            if title and "bing.com" not in href:
                title_map[href] = unescape(title)

        for r in results:
            if not r.title and r.url in title_map:
                r.title = title_map[r.url][:200]

        return results[:max_results]

    except SearchError:
        raise
    except Exception as e:
        raise SearchError(f"Bing search failed: {e}")
