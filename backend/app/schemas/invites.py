from datetime import datetime
import uuid

from pydantic import BaseModel, EmailStr, field_validator


class InviteCreate(BaseModel):
    email: EmailStr
    role: str = "member"


class InviteResponse(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    expires_at: datetime
    accepted_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class InviteAccept(BaseModel):
    token: str
    full_name: str
    password: str

    @field_validator("token", "full_name", "password")
    @classmethod
    def no_null_bytes(cls, v: str) -> str:
        if "\x00" in v:
            raise ValueError("must not contain null bytes")
        return v
