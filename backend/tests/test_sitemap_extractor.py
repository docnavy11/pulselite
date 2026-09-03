from unittest.mock import AsyncMock, MagicMock, patch

import httpx
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
    mock.status_code = 200
    return mock


@pytest.mark.asyncio
async def test_extract_urls_from_urlset():
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=_mock_response(URLSET_XML))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    with patch("app.services.ingestion.extractors.sitemap_extractor.httpx.AsyncClient", return_value=mock_client):
        urls = await extract_urls_from_sitemap("https://example.com/sitemap.xml")
    assert len(urls) == 3
    assert "https://example.com/about" in urls
    assert "https://example.com/pricing" in urls


@pytest.mark.asyncio
async def test_extract_urls_respects_max_urls():
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=_mock_response(URLSET_XML))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    with patch("app.services.ingestion.extractors.sitemap_extractor.httpx.AsyncClient", return_value=mock_client):
        urls = await extract_urls_from_sitemap("https://example.com/sitemap.xml", max_urls=2)
    assert len(urls) == 2


@pytest.mark.asyncio
async def test_extract_urls_from_sitemap_index():
    responses = [_mock_response(INDEX_XML), _mock_response(URLSET_XML)]
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=responses)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    with patch("app.services.ingestion.extractors.sitemap_extractor.httpx.AsyncClient", return_value=mock_client):
        urls = await extract_urls_from_sitemap("https://example.com/sitemap-index.xml")
    assert len(urls) == 3


@pytest.mark.asyncio
async def test_extract_urls_raises_on_http_error():
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.HTTPError("timeout"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    with patch("app.services.ingestion.extractors.sitemap_extractor.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(ValueError, match="Failed to fetch sitemap"):
            await extract_urls_from_sitemap("https://example.com/sitemap.xml")


@pytest.mark.asyncio
async def test_extract_urls_raises_on_invalid_xml():
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=_mock_response("not xml"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    with patch("app.services.ingestion.extractors.sitemap_extractor.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(ValueError, match="Invalid XML"):
            await extract_urls_from_sitemap("https://example.com/sitemap.xml")


@pytest.mark.asyncio
async def test_extract_urls_no_infinite_loop_on_cycle():
    """A sitemap that points to itself should not recurse infinitely."""
    self_referential = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://example.com/sitemap.xml</loc></sitemap>
</sitemapindex>"""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=_mock_response(self_referential))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    with patch("app.services.ingestion.extractors.sitemap_extractor.httpx.AsyncClient", return_value=mock_client):
        # Should return empty (cycle detected) without raising RecursionError
        urls = await extract_urls_from_sitemap("https://example.com/sitemap.xml")
    assert urls == []
