import hashlib
import secrets
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_keys import ApiKey

KEY_PREFIX = "pk_live_"


def _generate_key() -> str:
    return KEY_PREFIX + secrets.token_urlsafe(32)


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


async def create_api_key(db: AsyncSession, workspace_id: uuid.UUID, name: str) -> tuple[ApiKey, str]:
    full_key = _generate_key()
    key_hash = _hash_key(full_key)
    key_prefix = full_key[:12] + "..."

    api_key = ApiKey(
        workspace_id=workspace_id,
        name=name,
        key_hash=key_hash,
        key_prefix=key_prefix,
    )
    db.add(api_key)
    await db.flush()
    return api_key, full_key


async def list_api_keys(db: AsyncSession, workspace_id: uuid.UUID) -> list[ApiKey]:
    result = await db.execute(
        select(ApiKey).where(ApiKey.workspace_id == workspace_id).order_by(ApiKey.created_at.desc())
    )
    return list(result.scalars().all())


async def revoke_api_key(db: AsyncSession, workspace_id: uuid.UUID, key_id: uuid.UUID) -> None:
    result = await db.execute(select(ApiKey).where(ApiKey.id == key_id, ApiKey.workspace_id == workspace_id))
    api_key = result.scalar_one_or_none()
    if api_key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    api_key.is_active = False
    await db.flush()


async def validate_api_key(db: AsyncSession, key: str) -> ApiKey:
    key_hash = _hash_key(key)
    result = await db.execute(
        select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active == True)  # noqa: E712
    )
    api_key = result.scalar_one_or_none()
    if api_key is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or revoked API key")

    api_key.last_used_at = datetime.now(timezone.utc)
    await db.flush()
    return api_key
