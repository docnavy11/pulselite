"""Tests for webhook delivery orchestration and retry logic."""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.webhook_delivery import WebhookDelivery


@pytest.mark.asyncio
async def test_fire_event_creates_delivery_rows(db, workspace):
    """fire_event should create WebhookDelivery rows and dispatch tasks."""
    from app.models.organizational import WorkspaceWebhook
    from app.services.webhooks import fire_event

    # Create a webhook in the test DB
    hook = WorkspaceWebhook(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        url="https://example.com/hook",
        event_types=["conversation.created"],
        is_active=True,
    )
    db.add(hook)
    await db.flush()

    mock_task = MagicMock()
    mock_task.delay = MagicMock()
    with patch("app.services.webhooks._get_deliver_task", return_value=mock_task):
        await fire_event(workspace.id, "conversation.created", {"foo": "bar"}, db_session=db)

    # Check delivery row was created
    from sqlalchemy import select
    result = await db.execute(
        select(WebhookDelivery).where(WebhookDelivery.webhook_id == hook.id)
    )
    delivery = result.scalar_one()
    assert delivery.status == "pending"
    assert delivery.event_type == "conversation.created"
    assert delivery.workspace_id == workspace.id
    mock_task.delay.assert_called_once_with(str(delivery.id))


@pytest.mark.asyncio
async def test_fire_event_skips_non_matching_events(db, workspace):
    """fire_event should not create deliveries for non-matching event types."""
    from app.models.organizational import WorkspaceWebhook
    from app.services.webhooks import fire_event

    hook = WorkspaceWebhook(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        url="https://example.com/hook",
        event_types=["conversation.resolved"],
        is_active=True,
    )
    db.add(hook)
    await db.flush()

    mock_task = MagicMock()
    mock_task.delay = MagicMock()
    with patch("app.services.webhooks._get_deliver_task", return_value=mock_task):
        await fire_event(workspace.id, "conversation.created", {"foo": "bar"}, db_session=db)

    mock_task.delay.assert_not_called()
