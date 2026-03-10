"""Fetch and extract Help Center articles from Zendesk via the REST API."""

from __future__ import annotations

import re
from typing import AsyncGenerator

import httpx
from cryptography.fernet import InvalidToken


def _strip_html(html: str) -> str:
    """Remove HTML tags and return plain text."""
    return re.sub(r"<[^>]+>", " ", html or "").strip()


async def extract_from_zendesk(source_url: str, workspace_id: str, db) -> AsyncGenerator[dict, None]:
    """
    Yield one dict per Zendesk Help Center article.

    source_url may be:
    - A subdomain string: "mycompany"
    - A Zendesk URL: "https://mycompany.zendesk.com"
    - A Help Center category/section URL: "https://mycompany.zendesk.com/hc/en-us/..."

    Each yielded dict has: {title, content, source_url}
    """
    from sqlalchemy import select
    from app.models.integrations import IntegrationConfig
    from app.config import settings

    result = await db.execute(
        select(IntegrationConfig).where(
            IntegrationConfig.workspace_id == workspace_id,
            IntegrationConfig.integration_type == "zendesk",
            IntegrationConfig.is_active == True,  # noqa: E712
        )
    )
    config_row = result.scalar_one_or_none()
    if not config_row:
        raise ValueError("Zendesk not connected for this workspace")

    subdomain = config_row.config.get("subdomain", "")
    access_token = config_row.config.get("access_token", "")

    # Decrypt token if Fernet-encrypted
    if settings.FERNET_KEY and access_token:
        try:
            from cryptography.fernet import Fernet

            f = Fernet(settings.FERNET_KEY.encode())
            access_token = f.decrypt(access_token.encode()).decode()
        except (InvalidToken, Exception):
            pass  # stored unencrypted

    headers = {"Authorization": f"Bearer {access_token}"}
    base_api_url = f"https://{subdomain}.zendesk.com/api/v2/help_center/articles.json"

    async with httpx.AsyncClient(timeout=30.0) as client:
        url: str | None = base_api_url
        while url:
            resp = await client.get(url, headers=headers, params={"page[size]": 100})
            resp.raise_for_status()
            data = resp.json()
            for article in data.get("articles", []):
                title = article.get("title", "")
                body = _strip_html(article.get("body", ""))
                html_url = article.get("html_url", "")
                if body.strip():
                    yield {
                        "title": title,
                        "content": f"{title}\n\n{body}",
                        "source_url": html_url,
                    }
            # Cursor-based pagination
            url = data.get("next_page")
