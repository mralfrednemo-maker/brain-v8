"""Standalone search diagnostic — testing Brave API and httpx-based alternatives.

Run: python test_search_standalone.py
"""
import asyncio
import os
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()


async def test_brave_api():
    """Test Brave Search API (our existing fallback, $0.01/query)."""
    import httpx

    api_key = os.environ.get("BRAVE_API_KEY", "")
    if not api_key:
        print("  SKIP: No BRAVE_API_KEY in .env")
        return False, 0

    queries = [
        "PCI DSS 4.0 breach notification timeline requirements",
        "GDPR Article 33 supervisory authority notification 72 hours",
        "EU AI Act Annex III high risk financial services 2026",
    ]

    total = 0
    async with httpx.AsyncClient() as client:
        for query in queries:
            print(f"\n  Query: {query[:60]}")
            resp = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": 5},
                headers={"X-Subscription-Token": api_key, "Accept": "application/json"},
                timeout=10,
            )
            print(f"  Status: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("web", {}).get("results", [])
                print(f"  Results: {len(results)}")
                for r in results[:3]:
                    print(f"    [{r.get('url','')[:60]}]")
                    print(f"      {r.get('title','')[:60]}")
                    print(f"      {r.get('description','')[:80]}")
                total += len(results)
            else:
                print(f"  Error: {resp.text[:200]}")

    return total > 0, total


async def test_brave_with_full_content():
    """Test Brave + httpx content fetch (the full evidence pipeline)."""
    import httpx
    from thinker.brave_search import brave_search
    from thinker.types import SearchResult

    api_key = os.environ.get("BRAVE_API_KEY", "")
    if not api_key:
        print("  SKIP: No BRAVE_API_KEY")
        return False

    query = "DORA regulation ICT risk management requirements financial entities"
    print(f"\n  Query: {query}")
    results = await brave_search(query, api_key=api_key)
    print(f"  Results: {len(results)}")
    for r in results[:5]:
        print(f"    URL:     {r.url[:70]}")
        print(f"    Title:   {r.title[:60]}")
        print(f"    Snippet: {r.snippet[:80]}")
        content_len = len(r.full_content) if r.full_content else 0
        print(f"    Content: {content_len} chars")
        print()

    return len(results) > 0


async def test_sonar_search():
    """Test Sonar Pro via OpenRouter (our repeat-topic search)."""
    from thinker.sonar_search import sonar_search

    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        print("  SKIP: No OPENROUTER_API_KEY")
        return False, 0

    query = "PCI DSS 4.0 breach notification timeline what changed from 3.2.1"
    print(f"\n  Query: {query}")
    results = await sonar_search(query, api_key=api_key)
    print(f"  Results: {len(results)}")
    for r in results[:3]:
        print(f"    URL:     {r.url[:70]}")
        print(f"    Title:   {r.title[:60]}")
        content = r.full_content or r.snippet
        print(f"    Content: {len(content)} chars")
        if content:
            print(f"    Preview: {content[:150]}...")
        print()

    return len(results) > 0, len(results)


async def main():
    print("Search Provider Diagnostics")
    print("=" * 60)

    # 1. Brave API
    print("\n" + "=" * 60)
    print("TEST 1: Brave Search API")
    print("=" * 60)
    brave_ok, brave_count = await test_brave_api()

    # 2. Brave full flow
    print("\n" + "=" * 60)
    print("TEST 2: Brave full flow (search + content fetch)")
    print("=" * 60)
    brave_full = await test_brave_with_full_content()

    # 3. Sonar Pro
    print("\n" + "=" * 60)
    print("TEST 3: Sonar Pro via OpenRouter")
    print("=" * 60)
    sonar_ok, sonar_count = await test_sonar_search()

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Brave API:        {'WORKS' if brave_ok else 'FAIL'} ({brave_count} results)")
    print(f"  Brave full flow:  {'WORKS' if brave_full else 'FAIL'}")
    print(f"  Sonar Pro:        {'WORKS' if sonar_ok else 'FAIL'} ({sonar_count} results)")
    print(f"  Playwright/Google: BLOCKED (CAPTCHA)")
    print(f"  Playwright/Bing:   BLOCKED (CAPTCHA)")
    print(f"  DuckDuckGo:        BLOCKED (403)")
    print()
    if brave_ok:
        print("  RECOMMENDATION: Use Brave API as primary search ($0.01/query)")
        print("                   Use Sonar Pro for repeat topics (already wired)")
        print("                   Remove Playwright search (all engines block it)")
    elif sonar_ok:
        print("  RECOMMENDATION: Use Sonar Pro as primary (more expensive)")
    else:
        print("  RECOMMENDATION: Fix API keys")


if __name__ == "__main__":
    asyncio.run(main())
