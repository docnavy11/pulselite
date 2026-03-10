"""Fetch and extract Knowledge articles from Salesforce via the REST API."""

from __future__ import annotations

from typing import AsyncGenerator

import httpx
from cryptography.fernet import InvalidToken


async def extract_from_salesforce(source_url: str, workspace_id: str, db) -> AsyncGenerator[dict, None]:
    """
    Yield one dict per published Salesforce Knowledge article.

    source_url is ignored — the extractor uses the IntegrationConfig stored
    for this workspace (connected via OAuth).

    Each yielded dict has: {title, content, source_url}
    """
    from sqlalchemy import select
    from app.models.integrations import IntegrationConfig
    from app.config import settings

    result = await db.execute(
        select(IntegrationConfig).where(
            IntegrationConfig.workspace_id == workspace_id,
            IntegrationConfig.integration_type == "salesforce",
            IntegrationConfig.is_active == True,  # noqa: E712
        )
    )
    config_row = result.scalar_one_or_none()
    if not config_row:
        raise ValueError("Salesforce not connected for this workspace")

    instance_url = config_row.config.get("instance_url", "")
    access_token = config_row.config.get("access_token", "")

    # Decrypt token if Fernet-encrypted
    if settings.FERNET_KEY and access_token:
        try:
            from cryptography.fernet import Fernet

            f = Fernet(settings.FERNET_KEY.encode())
            access_token = f.decrypt(access_token.encode()).decode()
        except (InvalidToken, Exception):
            pass  # stored unencrypted

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    soql = "SELECT Id,Title,Summary,ArticleBody FROM Knowledge__kav WHERE PublishStatus='Online' LIMIT 200"
    query_url = f"{instance_url}/services/data/v58.0/query"

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(query_url, headers=headers, params={"q": soql})

        if resp.status_code == 400:
            # Try alternative Knowledge object name
            soql_alt = (
                "SELECT Id,Title,Summary,Body FROM KnowledgeArticleVersion WHERE PublishStatus='Online' LIMIT 200"
            )
            resp = await client.get(query_url, headers=headers, params={"q": soql_alt})

        resp.raise_for_status()
        data = resp.json()

        for record in data.get("records", []):
            title = record.get("Title", "")
            body = record.get("ArticleBody") or record.get("Body") or record.get("Summary") or ""
            if body.strip():
                yield {
                    "title": title,
                    "content": f"{title}\n\n{body}",
                    "source_url": f"{instance_url}/{record.get('Id', '')}",
                }
