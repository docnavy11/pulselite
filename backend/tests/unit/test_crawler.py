# backend/tests/unit/test_crawler.py
import pytest
from unittest.mock import patch

from app.services.crawler import CrawlResult, _normalize, _same_domain, discover_urls
from app.services.fetcher import FetchResult


def _make_fetch_result(url: str, html: str = "", status: int = 200) -> FetchResult:
    return FetchResult(url=url, html=html, text="content", title=None,
                       theme_color=None, status_code=status, used_playwright=False)


# ── _normalize ────────────────────────────────────────────────────────────────

def test_normalize_strips_fragment():
    assert _normalize("https://a.com/page#section") == "https://a.com/page"

def test_normalize_strips_query():
    assert _normalize("https://a.com/page?foo=bar") == "https://a.com/page"

def test_normalize_strips_trailing_slash():
    assert _normalize("https://a.com/page/") == "https://a.com/page"

def test_normalize_keeps_root():
    assert _normalize("https://a.com/") == "https://a.com/"


# ── _same_domain ──────────────────────────────────────────────────────────────

def test_same_domain_true():
    assert _same_domain("https://a.com/page", "a.com") is True

def test_same_domain_false():
    assert _same_domain("https://b.com/page", "a.com") is False


# ── discover_urls: sitemap strategy ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_discover_uses_sitemap_when_available():
    sitemap_xml = """<?xml version="1.0"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://a.com/page1</loc></url>
      <url><loc>https://a.com/page2</loc></url>
      <url><loc>https://a.com/page3</loc></url>
      <url><loc>https://a.com/page4</loc></url>
    </urlset>"""

    async def mock_fetch(url: str) -> FetchResult:
        if "sitemap" in url:
            return FetchResult(url=url, html=sitemap_xml, text="", title=None,
                               theme_color=None, status_code=200, used_playwright=False)
        return _make_fetch_result(url)

    with patch("app.services.crawler.fetch", side_effect=mock_fetch):
        result = await discover_urls("https://a.com", max_pages=10)

    assert result.used_sitemap is True
    assert len(result.urls) == 4
    assert result.over_limit is False


@pytest.mark.asyncio
async def test_over_limit_flag():
    sitemap_xml = """<?xml version="1.0"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://a.com/p1</loc></url>
      <url><loc>https://a.com/p2</loc></url>
      <url><loc>https://a.com/p3</loc></url>
      <url><loc>https://a.com/p4</loc></url>
      <url><loc>https://a.com/p5</loc></url>
    </urlset>"""

    async def mock_fetch(url: str) -> FetchResult:
        if "sitemap" in url:
            return FetchResult(url=url, html=sitemap_xml, text="", title=None,
                               theme_color=None, status_code=200, used_playwright=False)
        return _make_fetch_result(url)

    with patch("app.services.crawler.fetch", side_effect=mock_fetch):
        result = await discover_urls("https://a.com", max_pages=3)

    assert result.over_limit is True
    assert result.total_discovered == 5
    assert len(result.urls) == 3


@pytest.mark.asyncio
async def test_sitemap_not_found_falls_back_to_bfs():
    page_html = """<html><body>
    <a href="/about">About</a>
    <a href="/contact">Contact</a>
    </body></html>"""

    async def mock_fetch(url: str) -> FetchResult:
        if "sitemap" in url:
            return FetchResult(url=url, html="", text="", title=None,
                               theme_color=None, status_code=404, used_playwright=False)
        return FetchResult(url=url, html=page_html, text="content", title=None,
                           theme_color=None, status_code=200, used_playwright=False)

    with patch("app.services.crawler.fetch", side_effect=mock_fetch):
        result = await discover_urls("https://a.com", max_pages=10)

    assert result.used_sitemap is False
    assert any("a.com" in u for u in result.urls)


@pytest.mark.asyncio
async def test_bfs_drops_off_domain_links():
    page_html = """<html><body>
    <a href="/internal">Internal</a>
    <a href="https://other.com/page">External</a>
    </body></html>"""

    async def mock_fetch(url: str) -> FetchResult:
        if "sitemap" in url:
            return FetchResult(url=url, html="", text="", title=None,
                               theme_color=None, status_code=404, used_playwright=False)
        return FetchResult(url=url, html=page_html, text="content", title=None,
                           theme_color=None, status_code=200, used_playwright=False)

    with patch("app.services.crawler.fetch", side_effect=mock_fetch):
        result = await discover_urls("https://a.com", max_pages=20)

    assert all("other.com" not in u for u in result.urls)


@pytest.mark.asyncio
async def test_bfs_drops_urls_with_query_strings():
    page_html = """<html><body>
    <a href="/page?foo=bar">Query URL</a>
    <a href="/clean">Clean URL</a>
    </body></html>"""

    async def mock_fetch(url: str) -> FetchResult:
        if "sitemap" in url:
            return FetchResult(url=url, html="", text="", title=None,
                               theme_color=None, status_code=404, used_playwright=False)
        return FetchResult(url=url, html=page_html, text="content", title=None,
                           theme_color=None, status_code=200, used_playwright=False)

    with patch("app.services.crawler.fetch", side_effect=mock_fetch):
        result = await discover_urls("https://a.com", max_pages=20)

    assert not any("foo=bar" in u for u in result.urls)
    assert any("clean" in u for u in result.urls)
