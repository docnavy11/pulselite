"""Fetch and extract text content from Dropbox files or folders."""

from __future__ import annotations

import json
from typing import AsyncGenerator

import httpx
from cryptography.fernet import InvalidToken

SUPPORTED_EXTENSIONS = {".txt", ".md", ".markdown", ".csv", ".rst"}
MAX_FILE_SIZE = 1_000_000  # 1MB


async def extract_from_dropbox(source_url: str, workspace_id: str, db) -> AsyncGenerator[str, None]:
    """
    Fetch and yield text content from Dropbox files in the given folder path.

    source_url: Dropbox folder path (e.g. "/My Knowledge" or "" for root)
    Yields text chunks from supported file types.
    """
    from sqlalchemy import select
    from app.models.integrations import IntegrationConfig
    from app.config import settings

    result = await db.execute(
        select(IntegrationConfig).where(
            IntegrationConfig.workspace_id == workspace_id,
            IntegrationConfig.integration_type == "dropbox",
        )
    )
    config_row = result.scalar_one_or_none()
    if not config_row:
        raise ValueError("Dropbox not connected for this workspace")

    access_token = config_row.config.get("access_token", "")

    # Decrypt access token if Fernet-encrypted
    if settings.FERNET_KEY and access_token:
        try:
            from cryptography.fernet import Fernet

            f = Fernet(settings.FERNET_KEY.encode())
            access_token = f.decrypt(access_token.encode()).decode()
        except (InvalidToken, Exception):
            pass  # stored unencrypted or already decrypted

    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

    # Determine the folder path from source_url
    folder_path = source_url.strip() if source_url.strip() else ""
    # Dropbox root folder is "", not "/"
    if folder_path == "/":
        folder_path = ""

    async with httpx.AsyncClient(timeout=30.0) as client:
        # List all files recursively
        cursor = None
        files = []
        while True:
            if cursor:
                resp = await client.post(
                    "https://api.dropboxapi.com/2/files/list_folder/continue",
                    headers=headers,
                    json={"cursor": cursor},
                )
            else:
                resp = await client.post(
                    "https://api.dropboxapi.com/2/files/list_folder",
                    headers=headers,
                    json={"path": folder_path, "recursive": True, "limit": 100},
                )
            resp.raise_for_status()
            data = resp.json()

            for entry in data.get("entries", []):
                if entry.get(".tag") == "file":
                    name = entry.get("name", "")
                    ext = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
                    size = entry.get("size", 0)
                    if ext in SUPPORTED_EXTENSIONS and size <= MAX_FILE_SIZE:
                        files.append(entry["path_lower"])

            if not data.get("has_more"):
                break
            cursor = data.get("cursor")

        # Download and yield each file's content
        for path in files:
            try:
                download_headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Dropbox-API-Arg": json.dumps({"path": path}),
                }
                dl_resp = await client.post(
                    "https://content.dropboxapi.com/2/files/download",
                    headers=download_headers,
                )
                dl_resp.raise_for_status()
                text = dl_resp.text
                if text.strip():
                    # Yield in ~1000-char chunks
                    for i in range(0, len(text), 1000):
                        yield text[i : i + 1000]
            except Exception:
                continue  # Skip files that fail to download
