"""Free Bing search via curl_cffi (no API key needed).

Uses curl_cffi to impersonate a real browser's TLS fingerprint, bypassing
Bing's CAPTCHA detection. The scope=web&FORM=HDRSC1 parameters force
English web results regardless of IP geolocation.
"""
from __future__ import annotations

import re
from html import unescape
from urllib.parse import quote_plus

from thinker.types import SearchResult


async def bing_search(query: str, max_results: int = 10) -> list[SearchResult]:
    """Search Bing via curl_cffi — free, no API key, bypasses CAPTCHA.

    Uses scope=web&FORM=HDRSC1 to force English web results regardless
    of IP geolocation (tested from EU IP, returns English results).
    """
    try:
        from curl_cffi import requests as curl_requests
    except ImportError:
        return []

    try:
        resp = curl_requests.get(
            "https://www.bing.com/search",
            params={"q": query, "scope": "web", "FORM": "HDRSC1"},
            headers={"Accept-Language": "en-US,en;q=0.9"},
            impersonate="chrome131",
            timeout=15,
        )

        html = resp.text
        if "captcha" in html.lower() and "b_algo" not in html.lower():
            return []

        # Parse b_algo result blocks
        algos = re.findall(r'<li class="b_algo"[^>]*>(.*?)</li>', html, re.DOTALL)
        results = []
        seen_urls = set()

        for block in algos:
            # Title + URL
            title_match = re.search(
                r'<h2[^>]*><a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', block, re.DOTALL
            )
            # Real URL from <cite>
            cite_match = re.search(r'<cite[^>]*>(.*?)</cite>', block, re.DOTALL)
            # Snippet
            snippet_match = re.search(r'<p[^>]*>(.*?)</p>', block, re.DOTALL)

            if not title_match:
                continue

            title = re.sub(r'<[^>]+>', '', title_match.group(2)).strip()
            title = unescape(title)

            # Prefer cite URL (real URL) over redirect href
            url = ""
            if cite_match:
                url = re.sub(r'<[^>]+>', '', cite_match.group(1)).strip()
                # cite shows "domain.com › path" — reconstruct URL
                url = url.replace(" › ", "/")
                if not url.startswith("http"):
                    url = "https://" + url
            if not url or "bing.com" in url:
                url = unescape(title_match.group(1))

            snippet = ""
            if snippet_match:
                snippet = re.sub(r'<[^>]+>', '', snippet_match.group(1)).strip()
                snippet = unescape(snippet)

            if url in seen_urls or "bing.com" in url or "microsoft.com" in url:
                continue
            seen_urls.add(url)

            results.append(SearchResult(
                url=url,
                title=title[:200],
                snippet=snippet[:500],
            ))

            if len(results) >= max_results:
                break

        return results

    except Exception:
        return []
