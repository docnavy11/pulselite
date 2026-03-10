# backend/app/services/crawler.py
import logging
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse, urlunparse

import defusedxml.ElementTree as ET

from app.services.fetcher import FetchResult, fetch

logger = logging.getLogger(__name__)


@dataclass
class CrawlResult:
    urls: list[str]
    total_discovered: int
    over_limit: bool
    used_sitemap: bool


def _normalize(url: str) -> str:
    """Strip fragment and query string; normalize trailing slash on non-root paths."""
    p = urlparse(url)
    path = p.path.rstrip("/") or "/"
    return urlunparse((p.scheme, p.netloc, path, "", "", ""))


def _same_domain(url: str, root_domain: str) -> bool:
    return urlparse(url).netloc == root_domain


async def _discover_via_sitemap(root_url: str) -> list[str] | None:
    sitemap_url = root_url.rstrip("/") + "/sitemap.xml"
    result: FetchResult = await fetch(sitemap_url)
    if result.status_code != 200 or not result.html:
        return None

    try:
        root_el = ET.fromstring(result.html.encode())
    except Exception:
        return None

    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls: list[str] = []

    # Sitemap index: recurse into child sitemaps
    for sitemap_el in root_el.findall(".//sm:sitemap/sm:loc", ns):
        loc_text = sitemap_el.text
        if not loc_text:
            continue
        child = await fetch(loc_text.strip())
        if child.status_code == 200 and child.html:
            try:
                child_root = ET.fromstring(child.html.encode())
                for loc in child_root.findall(".//sm:url/sm:loc", ns):
                    if loc.text:
                        urls.append(loc.text.strip())
            except Exception:
                pass

    # Regular sitemap entries
    for loc in root_el.findall(".//sm:url/sm:loc", ns):
        if loc.text:
            urls.append(loc.text.strip())

    return urls if urls else None


async def _discover_via_bfs(root_url: str, max_depth: int = 3) -> list[str]:
    from bs4 import BeautifulSoup

    root_domain = urlparse(root_url).netloc
    visited: set[str] = set()
    queue: list[tuple[str, int]] = [(root_url, 0)]
    found: list[str] = []

    while queue:
        url, depth = queue.pop(0)
        norm = _normalize(url)
        if norm in visited:
            continue
        visited.add(norm)
        found.append(norm)

        if depth >= max_depth:
            continue

        result = await fetch(url)
        if result.status_code >= 400 or not result.html:
            continue

        soup = BeautifulSoup(result.html, "html.parser")
        for tag in soup.find_all("a", href=True):
            href = tag["href"]
            absolute = urljoin(url, href)
            parsed = urlparse(absolute)
            # Drop URLs with query strings entirely
            if parsed.query:
                continue
            norm_link = _normalize(absolute)
            if _same_domain(norm_link, root_domain) and norm_link not in visited:
                queue.append((norm_link, depth + 1))

    return found


async def discover_urls(root_url: str, max_pages: int) -> CrawlResult:
    """Discover all URLs under root_url up to max_pages."""
    urls: list[str] = []
    used_sitemap = False

    sitemap_urls = await _discover_via_sitemap(root_url)
    if sitemap_urls and len(sitemap_urls) >= 3:
        root_domain = urlparse(root_url).netloc
        urls = [u for u in sitemap_urls if _same_domain(u, root_domain)]
        used_sitemap = True
    else:
        urls = await _discover_via_bfs(root_url)

    # Deduplicate preserving order
    seen: set[str] = set()
    deduped: list[str] = []
    for u in urls:
        n = _normalize(u)
        if n not in seen:
            seen.add(n)
            deduped.append(u)

    total = len(deduped)
    return CrawlResult(
        urls=deduped[:max_pages],
        total_discovered=total,
        over_limit=total > max_pages,
        used_sitemap=used_sitemap,
    )
