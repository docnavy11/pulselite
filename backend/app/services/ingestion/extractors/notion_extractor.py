"""Fetch and extract text content from a Notion page via the Notion API."""

from __future__ import annotations

import re
from typing import Any

import httpx

NOTION_API_VERSION = "2022-06-28"
BLOCK_RENDERERS: dict[str, str] = {
    "paragraph": "rich_text",
    "heading_1": "rich_text",
    "heading_2": "rich_text",
    "heading_3": "rich_text",
    "bulleted_list_item": "rich_text",
    "numbered_list_item": "rich_text",
    "quote": "rich_text",
    "callout": "rich_text",
    "code": "rich_text",
    "toggle": "rich_text",
}


def _extract_rich_text(rich_text_items: list[dict]) -> str:
    return "".join(item.get("plain_text", "") for item in rich_text_items)


def _extract_block_text(block: dict) -> str:
    block_type = block.get("type", "")
    if block_type in BLOCK_RENDERERS:
        items = block.get(block_type, {}).get(BLOCK_RENDERERS[block_type], [])
        return _extract_rich_text(items)
    return ""


def _page_id_from_url(url: str) -> str:
    """Extract page ID from Notion URL like https://notion.so/workspace/Title-abc123def456"""
    # Match 32 hex chars at end (with or without hyphens)
    match = re.search(
        r"([0-9a-f]{32}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$",
        url.rstrip("/"),
    )
    if match:
        return match.group(1).replace("-", "")
    raise ValueError(f"Could not extract Notion page ID from URL: {url}")


async def _get_blocks(client: httpx.AsyncClient, block_id: str, depth: int = 0) -> list[str]:
    """Recursively fetch block content up to depth 3."""
    if depth > 3:
        return []

    lines: list[str] = []
    cursor = None
    while True:
        params: dict[str, Any] = {"page_size": 100}
        if cursor:
            params["start_cursor"] = cursor

        resp = await client.get(
            f"https://api.notion.com/v1/blocks/{block_id}/children",
            params=params,
        )
        if resp.status_code != 200:
            break

        data = resp.json()
        for block in data.get("results", []):
            text = _extract_block_text(block)
            if text.strip():
                lines.append(text.strip())
            if block.get("has_children"):
                child_lines = await _get_blocks(client, block["id"], depth + 1)
                lines.extend(child_lines)

        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")

    return lines


async def extract_from_notion(page_url: str, access_token: str) -> str:
    """Fetch a Notion page and return its plain text content."""
    page_id = _page_id_from_url(page_url)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Notion-Version": NOTION_API_VERSION,
    }
    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        # Get page title
        page_resp = await client.get(f"https://api.notion.com/v1/pages/{page_id}")
        title = ""
        if page_resp.status_code == 200:
            props = page_resp.json().get("properties", {})
            for prop in props.values():
                if prop.get("type") == "title":
                    title = _extract_rich_text(prop.get("title", []))
                    break

        lines = await _get_blocks(client, page_id)

    content = "\n".join(lines)
    if title:
        content = f"# {title}\n\n{content}"
    return content
