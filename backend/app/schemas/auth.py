import uuid

from pydantic import BaseModel, EmailStr, field_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str
    workspace_name: str

    @field_validator("workspace_name", "name")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must not be empty")
        if "\x00" in v:
            raise ValueError("must not contain null bytes")
        return v

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must not be empty")
        if "\x00" in v:
            raise ValueError("must not contain null bytes")
        if len(v) < 8:
            raise ValueError("must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("must contain at least one digit")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    totp_code: str | None = None


class TwoFARequiredResponse(BaseModel):
    requires_2fa: bool = True


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    display_name: str | None = None
    avatar_url: str | None = None

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    user: UserResponse
    tokens: TokenResponse
