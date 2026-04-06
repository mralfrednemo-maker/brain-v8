"""Primary search via Playwright Bing (headful browser).

Uses a real browser to search Bing, extracting results from the rendered DOM.
This is resilient to HTML structure changes and avoids CAPTCHA blocks that
affect curl_cffi/httpx approaches.

Headful mode is required — headless Chromium gets fingerprinted by Bing.
"""
from __future__ import annotations

import asyncio
from urllib.parse import quote_plus

from brain.types import SearchResult


def _cite_to_url(cite_text: str) -> str:
    """Convert Bing cite text to a real URL.

    Bing cite tags show: 'https://www.example.com › path › page'
    Convert to: 'https://www.example.com/path/page'
    """
    if not cite_text:
        return ""
    # Replace ' › ' separators with '/'
    url = cite_text.replace(" › ", "/").replace("›", "/").strip()
    # Ensure it starts with https://
    if not url.startswith("http"):
        url = "https://" + url
    return url


async def bing_search(query: str, max_results: int = 10) -> list[SearchResult]:
    """Search Bing via Playwright headful browser.

    Returns up to max_results SearchResult items with titles and snippets
    in Bing's ranking order. Raises SearchError on failure.
    """
    from brain.brave_search import SearchError

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise SearchError("Bing search requires playwright: pip install playwright && playwright install chromium")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
            )

            url = f"https://www.bing.com/search?q={quote_plus(query)}&scope=web&FORM=HDRSC1"
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)

            # Check for CAPTCHA
            page_content = await page.content()
            if "captcha" in page_content.lower() and "b_algo" not in page_content.lower():
                await browser.close()
                raise SearchError(f"Bing CAPTCHA block for: {query[:50]}")

            # Extract results from rendered DOM
            raw_results = await page.evaluate("""() => {
                const items = document.querySelectorAll('li.b_algo');
                return Array.from(items).map(item => {
                    const a = item.querySelector('h2 a');
                    const cite = item.querySelector('cite');
                    const snippet = item.querySelector('.b_caption p, .b_lineclamp2, .b_paractl');
                    return {
                        title: a ? a.innerText : '',
                        cite: cite ? cite.innerText : '',
                        snippet: snippet ? snippet.innerText : '',
                    };
                });
            }""")

            await browser.close()

            # Build results using cite-based URLs (real URLs, not redirects)
            results: list[SearchResult] = []
            seen_urls: set[str] = set()
            for item in raw_results:
                real_url = _cite_to_url(item.get("cite", ""))
                if not real_url or real_url in seen_urls:
                    continue
                seen_urls.add(real_url)
                results.append(SearchResult(
                    url=real_url,
                    title=item.get("title", "")[:200],
                    snippet=item.get("snippet", "")[:500],
                ))
                if len(results) >= max_results:
                    break

            return results

    except SearchError:
        raise
    except Exception as e:
        raise SearchError(f"Bing search failed: {e}")
