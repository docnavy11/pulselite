import pytest
from unittest.mock import patch

from app.services.crawler import DiscoveredUrl, _matches_paths, _normalize, _same_domain, discover_urls
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


# ── _matches_paths ────────────────────────────────────────────────────────────

def test_matches_paths_no_filter():
    assert _matches_paths("https://a.com/anything", [], []) is True

def test_matches_paths_include_match():
    assert _matches_paths("https://a.com/blog/post", ["/blog"], []) is True

def test_matches_paths_include_no_match():
    assert _matches_paths("https://a.com/about", ["/blog"], []) is False

def test_matches_paths_exclude_match():
    assert _matches_paths("https://a.com/admin/panel", [], ["/admin"]) is False

def test_matches_paths_exclude_no_match():
    assert _matches_paths("https://a.com/public", [], ["/admin"]) is True

def test_matches_paths_include_and_exclude():
    # In include AND not in exclude → True
    assert _matches_paths("https://a.com/docs/api", ["/docs"], ["/docs/private"]) is True

def test_matches_paths_include_and_excluded():
    # In include but also in exclude → False
    assert _matches_paths("https://a.com/docs/private/secret", ["/docs"], ["/docs/private"]) is False


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
        urls = await discover_urls("https://a.com")

    assert len(urls) == 4
    assert all("a.com" in d.url for d in urls)


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
        urls = await discover_urls("https://a.com")

    assert any("a.com" in d.url for d in urls)


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
        urls = await discover_urls("https://a.com")

    assert all("other.com" not in d.url for d in urls)


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
        urls = await discover_urls("https://a.com")

    assert not any("foo=bar" in d.url for d in urls)
    assert any("clean" in d.url for d in urls)


@pytest.mark.asyncio
async def test_sitemap_deduplicates_urls():
    sitemap_xml = """<?xml version="1.0"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://a.com/page</loc></url>
      <url><loc>https://a.com/page</loc></url>
      <url><loc>https://a.com/other1</loc></url>
      <url><loc>https://a.com/other2</loc></url>
    </urlset>"""

    async def mock_fetch(url: str) -> FetchResult:
        if "sitemap" in url:
            return FetchResult(url=url, html=sitemap_xml, text="", title=None,
                               theme_color=None, status_code=200, used_playwright=False)
        return _make_fetch_result(url)

    with patch("app.services.crawler.fetch", side_effect=mock_fetch):
        urls = await discover_urls("https://a.com")

    assert len(urls) == 3


@pytest.mark.asyncio
async def test_sitemap_index_recurses_into_child_sitemaps():
    index_xml = """<?xml version="1.0"?>
    <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <sitemap><loc>https://a.com/sitemap-child.xml</loc></sitemap>
    </sitemapindex>"""

    child_xml = """<?xml version="1.0"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://a.com/page1</loc></url>
      <url><loc>https://a.com/page2</loc></url>
      <url><loc>https://a.com/page3</loc></url>
    </urlset>"""

    async def mock_fetch(url: str) -> FetchResult:
        if url.endswith("sitemap-child.xml"):
            return FetchResult(url=url, html=child_xml, text="", title=None,
                               theme_color=None, status_code=200, used_playwright=False)
        if "sitemap" in url:
            return FetchResult(url=url, html=index_xml, text="", title=None,
                               theme_color=None, status_code=200, used_playwright=False)
        return _make_fetch_result(url)

    with patch("app.services.crawler.fetch", side_effect=mock_fetch):
        urls = await discover_urls("https://a.com")

    assert len(urls) == 3


# ── Path filter integration tests ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_include_paths_filters_sitemap_urls():
    sitemap_xml = """<?xml version="1.0"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://a.com/blog/post1</loc></url>
      <url><loc>https://a.com/blog/post2</loc></url>
      <url><loc>https://a.com/about</loc></url>
    </urlset>"""

    async def mock_fetch(url: str) -> FetchResult:
        if "sitemap" in url:
            return FetchResult(url=url, html=sitemap_xml, text="", title=None,
                               theme_color=None, status_code=200, used_playwright=False)
        return _make_fetch_result(url)

    with patch("app.services.crawler.fetch", side_effect=mock_fetch):
        urls = await discover_urls("https://a.com", include_paths=["/blog"])

    assert all("/blog" in d.url for d in urls)
    assert not any("/about" in d.url for d in urls)


@pytest.mark.asyncio
async def test_bfs_results_include_prefetched_content():
    """BFS-discovered pages should carry pre-fetched text so Phase 2 can skip re-fetching."""
    page_html = "<html><body>Hello world content here</body></html>"

    async def mock_fetch(url: str) -> FetchResult:
        if "sitemap" in url:
            return FetchResult(url=url, html="", text="", title=None,
                               theme_color=None, status_code=404, used_playwright=False)
        return FetchResult(url=url, html=page_html, text="Hello world content here", title="Home",
                           theme_color=None, status_code=200, used_playwright=False)

    with patch("app.services.crawler.fetch", side_effect=mock_fetch):
        urls = await discover_urls("https://a.com")

    root = next(d for d in urls if d.url == "https://a.com/")
    assert root.prefetched_text == "Hello world content here"
    assert root.prefetched_title == "Home"


@pytest.mark.asyncio
async def test_sitemap_results_have_no_prefetched_content():
    """Sitemap-discovered pages have no pre-fetched content — they're fetched in Phase 2."""
    sitemap_xml = """<?xml version="1.0"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://a.com/page1</loc></url>
      <url><loc>https://a.com/page2</loc></url>
      <url><loc>https://a.com/page3</loc></url>
    </urlset>"""

    async def mock_fetch(url: str) -> FetchResult:
        if "sitemap" in url:
            return FetchResult(url=url, html=sitemap_xml, text="", title=None,
                               theme_color=None, status_code=200, used_playwright=False)
        return _make_fetch_result(url)

    with patch("app.services.crawler.fetch", side_effect=mock_fetch):
        urls = await discover_urls("https://a.com")

    assert all(d.prefetched_text is None for d in urls)


@pytest.mark.asyncio
async def test_exclude_paths_filters_sitemap_urls():
    sitemap_xml = """<?xml version="1.0"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://a.com/public/page1</loc></url>
      <url><loc>https://a.com/admin/panel</loc></url>
      <url><loc>https://a.com/public/page2</loc></url>
      <url><loc>https://a.com/public/page3</loc></url>
    </urlset>"""

    async def mock_fetch(url: str) -> FetchResult:
        if "sitemap" in url:
            return FetchResult(url=url, html=sitemap_xml, text="", title=None,
                               theme_color=None, status_code=200, used_playwright=False)
        return _make_fetch_result(url)

    with patch("app.services.crawler.fetch", side_effect=mock_fetch):
        urls = await discover_urls("https://a.com", exclude_paths=["/admin"])

    assert not any("/admin" in d.url for d in urls)
    assert len(urls) == 3
