from urllib.parse import urlparse

import defusedxml.ElementTree as ET
import httpx

_SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"


def _validate_url_scheme(url: str) -> None:
    """Raise ValueError if the URL scheme is not http or https (prevents SSRF)."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Disallowed URL scheme '{parsed.scheme}' in sitemap URL: {url}")


async def extract_urls_from_sitemap(
    sitemap_url: str,
    max_urls: int = 200,
    _visited: set[str] | None = None,
) -> list[str]:
    """Fetch sitemap XML and return all <loc> URLs (recurses into sitemap indexes)."""
    _validate_url_scheme(sitemap_url)

    if _visited is None:
        _visited = set()

    if sitemap_url in _visited:
        return []
    _visited.add(sitemap_url)

    try:
        async with httpx.AsyncClient(timeout=30.0, max_redirects=5) as client:
            response = await client.get(sitemap_url, follow_redirects=True)
            response.raise_for_status()
    except httpx.HTTPError as e:
        raise ValueError(f"Failed to fetch sitemap {sitemap_url}: {e}") from e

    try:
        root = ET.fromstring(response.text)
    except ET.ParseError as e:
        raise ValueError(f"Invalid XML in sitemap {sitemap_url}: {e}") from e

    ns = {"sm": _SITEMAP_NS}
    urls: list[str] = []

    # Sitemap index — recurse into child sitemaps
    for sitemap_tag in root.findall("sm:sitemap", ns):
        loc = sitemap_tag.find("sm:loc", ns)
        if loc is not None and loc.text:
            child_urls = await extract_urls_from_sitemap(loc.text.strip(), max_urls - len(urls), _visited)
            urls.extend(child_urls)
            if len(urls) >= max_urls:
                break

    # Regular urlset
    for url_tag in root.findall("sm:url", ns):
        loc = url_tag.find("sm:loc", ns)
        if loc is not None and loc.text:
            urls.append(loc.text.strip())
            if len(urls) >= max_urls:
                break

    return urls[:max_urls]
