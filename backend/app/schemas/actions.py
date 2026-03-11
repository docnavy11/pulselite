import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator


class ActionCreate(BaseModel):
    action_type: Literal[
        "collect_lead", "webhook", "custom_button", "slack_message", "web_search",
        "calendly", "calcom", "custom_tool", "stripe_lookup", "salesforce_ticket"
    ]
    name: str
    trigger_description: str
    config: dict = {}
    is_enabled: bool = True
    parameters: list[dict] = []

    @field_validator("name", "trigger_description")
    @classmethod
    def no_null_bytes(cls, v: str) -> str:
        if "\x00" in v:
            raise ValueError("must not contain null bytes")
        return v


class ActionResponse(BaseModel):
    id: uuid.UUID
    chatbot_id: uuid.UUID
    action_type: str
    name: str
    trigger_description: str
    config: dict
    is_enabled: bool
    parameters: list[dict]
    created_at: datetime

    model_config = {"from_attributes": True}


class ActionUpdate(BaseModel):
    name: str | None = None
    trigger_description: str | None = None
    config: dict | None = None
    is_enabled: bool | None = None
    parameters: list[dict] | None = None
