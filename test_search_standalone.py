"""Search diagnostic — Bing httpx deep dive.

Run: python test_search_standalone.py
"""
import asyncio
import re
from urllib.parse import quote_plus, unquote

import httpx


QUERIES = [
    "PCI DSS 4.0 breach notification timeline requirements",
    "GDPR Article 33 supervisory authority notification 72 hours",
    "EU AI Act Annex III high risk financial services",
]


async def bing_search_httpx(query: str, max_results: int = 10) -> list[dict]:
    """Search Bing via direct HTTP — no browser needed."""
    async with httpx.AsyncClient(follow_redirects=True) as client:
        resp = await client.get(
            "https://www.bing.com/search",
            params={"q": query, "count": max_results, "setlang": "en", "mkt": "en-US", "cc": "US"},
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                              "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9",
            },
            timeout=10,
        )

        html = resp.text
        if "captcha" in html.lower() or "verify you are human" in html.lower():
            return []

        # Save for debugging
        with open("debug_bing_raw.html", "w", encoding="utf-8") as f:
            f.write(html)

        # Strategy 1: Extract from <li class="b_algo"> blocks
        results = []
        # Find all b_algo blocks
        algo_blocks = re.findall(r'<li class="b_algo"[^>]*>(.*?)</li>', html, re.DOTALL)

        for block in algo_blocks:
            # Extract URL from <a href="...">
            url_match = re.search(r'<a[^>]+href="(https?://[^"]+)"', block)
            # Extract title from <a>...</a>
            title_match = re.search(r'<a[^>]+href="https?://[^"]+"[^>]*>(.*?)</a>', block, re.DOTALL)
            # Extract snippet from <p> or <span class="b_algoSlug">
            snippet_match = re.search(r'<p[^>]*>(.*?)</p>', block, re.DOTALL)

            if url_match:
                url = url_match.group(1)
                # Resolve Bing redirect URLs
                if "bing.com/ck/a" in url:
                    # Try to extract real URL from the redirect parameters
                    u_match = re.search(r'[?&]u=a1(.*?)(?:&|$)', url)
                    if u_match:
                        try:
                            url = unquote(u_match.group(1))
                        except Exception:
                            pass

                title = ""
                if title_match:
                    title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()

                snippet = ""
                if snippet_match:
                    snippet = re.sub(r'<[^>]+>', '', snippet_match.group(1)).strip()

                if "bing.com" not in url and "microsoft.com" not in url:
                    results.append({"url": url, "title": title, "snippet": snippet})

        # Strategy 2: If b_algo failed, try broader pattern
        if not results:
            # Look for any external links in the main content area
            all_urls = re.findall(r'href="(https?://(?!.*bing\.com)(?!.*microsoft\.com)[^"]+)"', html)
            seen = set()
            for url in all_urls:
                if url not in seen and "bing.com" not in url:
                    seen.add(url)
                    results.append({"url": url, "title": "", "snippet": ""})

        return results[:max_results]


async def main():
    print("=" * 60)
    print("Bing httpx Search — Deep Dive")
    print("=" * 60)

    total = 0
    for q in QUERIES:
        print(f"\nQuery: {q}")
        print("-" * 50)
        results = await bing_search_httpx(q)
        print(f"  Results: {len(results)}")
        for r in results[:5]:
            print(f"  URL:     {r['url'][:70]}")
            print(f"  Title:   {r['title'][:60]}")
            print(f"  Snippet: {r['snippet'][:80]}")
            print()
        total += len(results)

    print("=" * 60)
    print(f"Total results: {total}")
    if total > 0:
        print("Bing httpx: WORKS")
    else:
        print("Bing httpx: FAIL — check debug_bing_raw.html")


if __name__ == "__main__":
    asyncio.run(main())
