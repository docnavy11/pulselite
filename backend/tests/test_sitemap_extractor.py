from unittest.mock import MagicMock, patch

import pytest

from app.services.ingestion.extractors.sitemap_extractor import extract_urls_from_sitemap

URLSET_XML = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/</loc></url>
  <url><loc>https://example.com/about</loc></url>
  <url><loc>https://example.com/pricing</loc></url>
</urlset>"""

INDEX_XML = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://example.com/sitemap-pages.xml</loc></sitemap>
</sitemapindex>"""


def _mock_response(text: str):
    mock = MagicMock()
    mock.text = text
    mock.raise_for_status = MagicMock()
    return mock


def test_extract_urls_from_urlset():
    with patch("httpx.get", return_value=_mock_response(URLSET_XML)):
        urls = extract_urls_from_sitemap("https://example.com/sitemap.xml")
    assert len(urls) == 3
    assert "https://example.com/about" in urls
    assert "https://example.com/pricing" in urls


def test_extract_urls_respects_max_urls():
    with patch("httpx.get", return_value=_mock_response(URLSET_XML)):
        urls = extract_urls_from_sitemap("https://example.com/sitemap.xml", max_urls=2)
    assert len(urls) == 2


def test_extract_urls_from_sitemap_index():
    responses = [_mock_response(INDEX_XML), _mock_response(URLSET_XML)]
    with patch("httpx.get", side_effect=responses):
        urls = extract_urls_from_sitemap("https://example.com/sitemap-index.xml")
    assert len(urls) == 3


def test_extract_urls_raises_on_http_error():
    import httpx
    with patch("httpx.get", side_effect=httpx.HTTPError("timeout")):
        with pytest.raises(ValueError, match="Failed to fetch sitemap"):
            extract_urls_from_sitemap("https://example.com/sitemap.xml")


def test_extract_urls_raises_on_invalid_xml():
    with patch("httpx.get", return_value=_mock_response("not xml")):
        with pytest.raises(ValueError, match="Invalid XML"):
            extract_urls_from_sitemap("https://example.com/sitemap.xml")


def test_extract_urls_no_infinite_loop_on_cycle():
    """A sitemap that points to itself should not recurse infinitely."""
    self_referential = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://example.com/sitemap.xml</loc></sitemap>
</sitemapindex>"""
    with patch("httpx.get", return_value=_mock_response(self_referential)):
        # Should return empty (cycle detected) without raising RecursionError
        urls = extract_urls_from_sitemap("https://example.com/sitemap.xml")
    assert urls == []
