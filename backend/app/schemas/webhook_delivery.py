import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class WebhookDeliveryResponse(BaseModel):
    id: uuid.UUID
    webhook_id: uuid.UUID
    event_type: str
    status: str
    attempts: int
    max_attempts: int
    next_retry_at: Optional[datetime] = None
    last_status_code: Optional[int] = None
    last_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WebhookDeliveryListResponse(BaseModel):
    items: list[WebhookDeliveryResponse]
    total: int
