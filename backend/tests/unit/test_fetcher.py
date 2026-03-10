# backend/tests/unit/test_fetcher.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.fetcher import FetchResult, fetch, extract_brand_color, _extract_theme_color


# ── extract_brand_color ───────────────────────────────────────────────────────

def test_extract_theme_color_from_meta():
    html = '<meta name="theme-color" content="#4F46E5">'
    assert _extract_theme_color(html) == "#4F46E5"

def test_extract_theme_color_reversed_attrs():
    html = '<meta content="#123ABC" name="theme-color">'
    assert _extract_theme_color(html) == "#123ABC"

def test_extract_theme_color_css_variable():
    html = "<style>:root { --primary: #6366f1; }</style>"
    assert _extract_theme_color(html) == "#6366f1"

def test_extract_theme_color_none_when_missing():
    assert _extract_theme_color("<html><body>no color</body></html>") is None

def test_extract_brand_color_empty_html():
    assert extract_brand_color("") is None


# ── fetch: SSRF guard ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_rejects_non_http_scheme():
    with pytest.raises(ValueError, match="http or https"):
        await fetch("file:///etc/passwd")

@pytest.mark.asyncio
async def test_fetch_rejects_ftp():
    with pytest.raises(ValueError, match="http or https"):
        await fetch("ftp://evil.com/file")


# ── fetch: httpx path ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_returns_result_on_200():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "<html><title>Acme</title><body>lots of content here " + "x" * 600 + "</body></html>"

    with patch("app.services.fetcher.trafilatura.extract", return_value="lots of content here " + "x" * 600):
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await fetch("https://example.com")

    assert result.status_code == 200
    assert result.title == "Acme"
    assert result.used_playwright is False
    assert len(result.text) > 500


@pytest.mark.asyncio
async def test_fetch_triggers_playwright_when_text_thin():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "<html><body>thin</body></html>"

    with patch("app.services.fetcher.trafilatura.extract", return_value="thin"):
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            with patch("app.services.fetcher._fetch_with_playwright", new_callable=AsyncMock) as mock_pw:
                mock_pw.return_value = ("<html><body>" + "rich content " * 100 + "</body></html>", "rich content " * 100)
                result = await fetch("https://example.com")

    assert result.used_playwright is True
    assert len(result.text) > 500


@pytest.mark.asyncio
async def test_fetch_returns_httpx_result_when_playwright_fails():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "<html><body>thin</body></html>"

    with patch("app.services.fetcher.trafilatura.extract", return_value="thin"):
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            with patch("app.services.fetcher._fetch_with_playwright", side_effect=Exception("browser crash")):
                result = await fetch("https://example.com")

    assert result.status_code == 200
    assert result.used_playwright is False


@pytest.mark.asyncio
async def test_fetch_returns_empty_on_network_error():
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=Exception("connection refused"))
        mock_client_cls.return_value = mock_client

        result = await fetch("https://example.com")

    assert result.text == ""
    assert result.html == ""
    assert result.status_code == 0
