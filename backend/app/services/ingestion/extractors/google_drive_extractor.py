"""Fetch and extract text content from Google Drive files or folders."""

from __future__ import annotations

import re

import httpx
from cryptography.fernet import InvalidToken


async def _refresh_access_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    """Use a refresh token to obtain a new access token from Google."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        if resp.status_code == 200:
            return resp.json().get("access_token", "")
    return ""


async def extract_from_google_drive(source_url: str, workspace_id: str, db) -> str:
    """
    Fetch and return the full text content of a Google Drive file or folder.

    source_url may be:
    - A Google Doc URL: https://docs.google.com/document/d/{doc_id}/edit
    - A Google Drive folder URL: https://drive.google.com/drive/folders/{folder_id}
    - A plain file ID string

    Returns extracted plain text for ingestion.
    """
    from sqlalchemy import select

    from app.config import settings
    from app.models.integrations import IntegrationConfig

    result = await db.execute(
        select(IntegrationConfig).where(
            IntegrationConfig.workspace_id == workspace_id,
            IntegrationConfig.integration_type == "google_drive",
            IntegrationConfig.is_active == True,  # noqa: E712
        )
    )
    config_row = result.scalar_one_or_none()
    if not config_row:
        raise ValueError("Google Drive not connected for this workspace")

    access_token = config_row.config.get("access_token", "")
    refresh_token = config_row.config.get("refresh_token", "")

    # Decrypt refresh token if Fernet-encrypted
    if settings.FERNET_KEY and refresh_token:
        try:
            from cryptography.fernet import Fernet

            f = Fernet(settings.FERNET_KEY.encode())
            refresh_token = f.decrypt(refresh_token.encode()).decode()
        except (InvalidToken, Exception):
            pass  # stored unencrypted or already decrypted

    headers = {"Authorization": f"Bearer {access_token}"}

    doc_match = re.search(r"/document/d/([a-zA-Z0-9_-]+)", source_url)
    folder_match = re.search(r"/folders/([a-zA-Z0-9_-]+)", source_url)

    if doc_match:
        file_id = doc_match.group(1)
    elif folder_match:
        file_id = folder_match.group(1)
    else:
        file_id = source_url.strip()

    parts: list[str] = []

    async with httpx.AsyncClient(timeout=30) as client:
        if folder_match:
            # List files in the folder (up to 100)
            resp = await client.get(
                "https://www.googleapis.com/drive/v3/files",
                params={
                    "q": f"'{file_id}' in parents and trashed = false",
                    "fields": "files(id,name,mimeType)",
                    "pageSize": 100,
                },
                headers=headers,
            )
            if resp.status_code == 401 and refresh_token:
                access_token = await _refresh_access_token(
                    settings.GOOGLE_DRIVE_CLIENT_ID,
                    settings.GOOGLE_DRIVE_CLIENT_SECRET,
                    refresh_token,
                )
                headers = {"Authorization": f"Bearer {access_token}"}
                resp = await client.get(
                    "https://www.googleapis.com/drive/v3/files",
                    params={
                        "q": f"'{file_id}' in parents and trashed = false",
                        "fields": "files(id,name,mimeType)",
                        "pageSize": 100,
                    },
                    headers=headers,
                )
            files = resp.json().get("files", []) if resp.status_code == 200 else []
            for f in files:
                text = await _extract_file(client, f["id"], f.get("mimeType", ""), headers)
                if text:
                    parts.append(f"## {f.get('name', f['id'])}\n\n{text}")
        else:
            # Single file
            meta_resp = await client.get(
                f"https://www.googleapis.com/drive/v3/files/{file_id}",
                params={"fields": "name,mimeType"},
                headers=headers,
            )
            if meta_resp.status_code == 401 and refresh_token:
                access_token = await _refresh_access_token(
                    settings.GOOGLE_DRIVE_CLIENT_ID,
                    settings.GOOGLE_DRIVE_CLIENT_SECRET,
                    refresh_token,
                )
                headers = {"Authorization": f"Bearer {access_token}"}
                meta_resp = await client.get(
                    f"https://www.googleapis.com/drive/v3/files/{file_id}",
                    params={"fields": "name,mimeType"},
                    headers=headers,
                )
            if meta_resp.status_code == 200:
                meta = meta_resp.json()
                text = await _extract_file(client, file_id, meta.get("mimeType", ""), headers)
                if text:
                    name = meta.get("name", "")
                    parts.append(f"# {name}\n\n{text}" if name else text)

    return "\n\n".join(parts)


async def _extract_file(
    client: httpx.AsyncClient,
    file_id: str,
    mime_type: str,
    headers: dict,
) -> str:
    """Export a Google Doc as plain text, or download text/csv files directly."""
    if mime_type == "application/vnd.google-apps.document":
        resp = await client.get(
            f"https://www.googleapis.com/drive/v3/files/{file_id}/export",
            params={"mimeType": "text/plain"},
            headers=headers,
        )
        if resp.status_code == 200:
            return resp.text
    elif mime_type in ("text/plain", "text/markdown", "text/csv"):
        resp = await client.get(
            f"https://www.googleapis.com/drive/v3/files/{file_id}",
            params={"alt": "media"},
            headers=headers,
        )
        if resp.status_code == 200:
            return resp.text
    # PDFs, images, spreadsheets, etc. are skipped for now
    return ""
