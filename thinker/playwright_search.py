"""Primary search via Playwright headless browser.

V8 spec Section 6: Google via Playwright headless ($0).
Parses URLs from Google results page, fetches full page content.
"""
from __future__ import annotations

from urllib.parse import quote_plus

from thinker.types import SearchResult


async def google_search(query: str, max_results: int = 10) -> list[SearchResult]:
    """Search Google via headless Playwright and return results with full page content."""
    from playwright.async_api import async_playwright

    results: list[SearchResult] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )

        url = f"https://www.google.com/search?q={quote_plus(query)}&num={max_results}"
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)

        links = await page.eval_on_selector_all(
            "div.g a[href]",
            "els => els.map(e => ({href: e.href, title: e.innerText}))",
        )

        seen_urls = set()
        for link in links:
            href = link.get("href", "")
            if not href.startswith("http") or href in seen_urls:
                continue
            if any(skip in href for skip in ["google.com", "youtube.com", "webcache"]):
                continue
            seen_urls.add(href)
            results.append(SearchResult(
                url=href, title=link.get("title", ""), snippet="",
            ))
            if len(results) >= max_results:
                break

        await browser.close()

    return results


async def fetch_page_content(url: str, max_chars: int = 50_000) -> str:
    """Fetch full page text content via Playwright."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            content = await page.inner_text("body")
            return content[:max_chars]
        except Exception:
            return ""
        finally:
            await browser.close()
