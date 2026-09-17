# backend/app/services/fetcher.py
import logging
import re
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
import trafilatura

logger = logging.getLogger(__name__)

_PLAYWRIGHT_THRESHOLD = 500
_USER_AGENT = "Mozilla/5.0 (compatible; PulseliteBot/1.0)"


@dataclass
class FetchResult:
    url: str
    html: str
    text: str
    title: str | None
    theme_color: str | None
    status_code: int
    used_playwright: bool


def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"URL must be http or https, got: {url!r}")


def _extract_title(html: str) -> str | None:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else None


def _extract_theme_color(html: str) -> str | None:
    """Extract hex color from meta theme-color or --primary CSS variable."""
    m = re.search(
        r'<meta[^>]+name=["\']theme-color["\'][^>]+content=["\']([^"\']+)["\']',
        html,
        re.IGNORECASE,
    )
    if not m:
        m = re.search(
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']theme-color["\']',
            html,
            re.IGNORECASE,
        )
    if m:
        color = m.group(1).strip()
        if re.match(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$", color):
            return color
    css_m = re.search(r"--primary\s*:\s*(#[0-9a-fA-F]{3,6})", html)
    if css_m:
        return css_m.group(1)
    return None


def extract_brand_color(html: str) -> str | None:
    """Public wrapper — returns None for empty input."""
    if not html:
        return None
    return _extract_theme_color(html)


async def _fetch_with_playwright(url: str) -> tuple[str, str]:
    """Returns (html, text). Caller handles exceptions."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            page = await browser.new_page(extra_http_headers={"User-Agent": _USER_AGENT})
            await page.goto(url, timeout=30_000)
            await page.wait_for_load_state("networkidle", timeout=15_000)
            html = await page.content()
            text = (
                trafilatura.extract(html, include_comments=False, include_tables=True, output_format="markdown") or ""
            )
            return html, text
        finally:
            await browser.close()


async def fetch(url: str) -> FetchResult:
    """Fetch URL content. Falls back to Playwright when text < 500 chars."""
    _validate_url(url)

    html = ""
    text = ""
    status_code = 0

    try:
        async with httpx.AsyncClient(
            headers={"User-Agent": _USER_AGENT},
            follow_redirects=True,
            timeout=10.0,
        ) as client:
            response = await client.get(url)
            status_code = response.status_code
            if response.status_code < 400:
                html = response.text
                text = (
                    trafilatura.extract(html, include_comments=False, include_tables=True, output_format="markdown")
                    or ""
                )
    except Exception as exc:
        logger.warning("httpx fetch failed for %s: %s", url, exc)
        return FetchResult(
            url=url,
            html="",
            text="",
            title=None,
            theme_color=None,
            status_code=0,
            used_playwright=False,
        )

    used_playwright = False
    if len(text) < _PLAYWRIGHT_THRESHOLD:
        try:
            html, text = await _fetch_with_playwright(url)
            used_playwright = True
        except Exception as exc:
            logger.warning("Playwright fallback failed for %s: %s", url, exc)

    return FetchResult(
        url=url,
        html=html,
        text=text,
        title=_extract_title(html),
        theme_color=_extract_theme_color(html),
        status_code=status_code,
        used_playwright=used_playwright,
    )
