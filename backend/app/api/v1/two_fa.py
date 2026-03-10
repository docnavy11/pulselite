"""TOTP-based two-factor authentication endpoints.

Routes (all user-level, not workspace-scoped):
  POST /api/v1/auth/2fa/setup    — generate a new TOTP secret, return QR URI
  POST /api/v1/auth/2fa/verify   — verify code and enable 2FA
  POST /api/v1/auth/2fa/disable  — verify code and disable 2FA
"""

import pyotp
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.organizational import Agent
from app.services.encryption import decrypt_api_key, encrypt_api_key

router = APIRouter(prefix="/auth/2fa", tags=["2fa"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class TotpCodeBody(BaseModel):
    code: str


class SetupResponse(BaseModel):
    secret: str
    qr_uri: str


class SuccessResponse(BaseModel):
    success: bool


class StatusResponse(BaseModel):
    two_fa_enabled: bool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _verify_totp(encrypted_secret: str, code: str) -> bool:
    """Decrypt the stored secret and verify the TOTP code."""
    secret = decrypt_api_key(encrypted_secret)
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/status", response_model=StatusResponse)
async def get_2fa_status(
    current_user: Agent = Depends(get_current_user),
):
    """Return the current 2FA status for the authenticated user."""
    return StatusResponse(two_fa_enabled=current_user.two_fa_enabled)


@router.post("/setup", response_model=SetupResponse)
async def setup_2fa(
    current_user: Agent = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate a new TOTP secret for the current user and return the provisioning URI.

    Does NOT enable 2FA yet — the user must call /verify with a valid code first.
    """
    secret = pyotp.random_base32()
    encrypted = encrypt_api_key(secret)

    current_user.totp_secret = encrypted
    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)

    qr_uri = pyotp.TOTP(secret).provisioning_uri(
        name=current_user.email,
        issuer_name="Pulse",
    )

    return SetupResponse(secret=secret, qr_uri=qr_uri)


@router.post("/verify", response_model=SuccessResponse)
async def verify_2fa(
    body: TotpCodeBody,
    current_user: Agent = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Verify the TOTP code and enable 2FA for the current user."""
    if not current_user.totp_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA setup not initiated. Call /setup first.",
        )

    if not _verify_totp(current_user.totp_secret, body.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid TOTP code",
        )

    current_user.two_fa_enabled = True
    db.add(current_user)
    await db.commit()

    return SuccessResponse(success=True)


@router.post("/disable", response_model=SuccessResponse)
async def disable_2fa(
    body: TotpCodeBody,
    current_user: Agent = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Verify the current TOTP code and disable 2FA, clearing the secret."""
    if not current_user.two_fa_enabled or not current_user.totp_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA is not enabled for this account.",
        )

    if not _verify_totp(current_user.totp_secret, body.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid TOTP code",
        )

    current_user.two_fa_enabled = False
    current_user.totp_secret = None
    db.add(current_user)
    await db.commit()

    return SuccessResponse(success=True)
