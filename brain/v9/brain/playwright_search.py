"""Primary search via Playwright headless browser.

Google via Playwright headless ($0).
Handles Google consent pages (EU cookie banners).
Parses URLs from Google results page, fetches full page content.
"""
from __future__ import annotations

from urllib.parse import quote_plus

from brain.types import SearchResult


async def _dismiss_consent(page) -> None:
    """Dismiss Google's cookie consent page if it appears."""
    try:
        # Look for consent buttons (various languages)
        for selector in [
            'button:has-text("Accept all")',
            'button:has-text("Αποδοχή όλων")',  # Greek
            'button:has-text("Alle akzeptieren")',  # German
            'button:has-text("Accepter tout")',  # French
            'button:has-text("Aceptar todo")',  # Spanish
            'form[action*="consent"] button',
            '#L2AGLb',  # Google's consent button ID
        ]:
            btn = page.locator(selector).first
            if await btn.is_visible(timeout=2000):
                await btn.click()
                await page.wait_for_load_state("domcontentloaded")
                return
    except Exception:
        pass


async def google_search(query: str, max_results: int = 10) -> list[SearchResult]:
    """Search Google via headless Playwright and return results with full page content."""
    from playwright.async_api import async_playwright

    results: list[SearchResult] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        # Use google.com with hl=en to avoid localized consent pages where possible
        url = f"https://www.google.com/search?q={quote_plus(query)}&num={max_results}&hl=en"
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)

        # Handle EU cookie consent if it appears
        await _dismiss_consent(page)

        # If still on consent page, try navigating again
        title = await page.title()
        if "consent" in title.lower() or "before you continue" in title.lower() or "Πριν" in title:
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)

        # Extract result links — try multiple selectors for resilience
        links = []
        for selector in ["div.g a[href]", "div#search a[href]", "a[data-ved][href]"]:
            links = await page.eval_on_selector_all(
                selector,
                "els => els.map(e => ({href: e.href, title: e.innerText}))",
            )
            if links:
                break

        # If structured selectors fail, fall back to all external links
        if not links:
            links = await page.eval_on_selector_all(
                "a[href]",
                "els => els.map(e => ({href: e.href, title: e.innerText}))",
            )

        seen_urls = set()
        for link in links:
            href = link.get("href", "")
            if not href.startswith("http") or href in seen_urls:
                continue
            if any(skip in href for skip in ["google.com", "google.", "youtube.com",
                                              "webcache", "accounts.google", "gstatic"]):
                continue
            seen_urls.add(href)
            results.append(SearchResult(
                url=href, title=link.get("title", "")[:200], snippet="",
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
