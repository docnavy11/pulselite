import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.actions import ChatbotAction


async def list_actions(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    chatbot_id: uuid.UUID,
) -> list[ChatbotAction]:
    result = await db.execute(
        select(ChatbotAction)
        .where(ChatbotAction.workspace_id == workspace_id, ChatbotAction.chatbot_id == chatbot_id)
        .order_by(ChatbotAction.created_at)
    )
    return list(result.scalars().all())


async def list_enabled_actions(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    chatbot_id: uuid.UUID,
) -> list[ChatbotAction]:
    result = await db.execute(
        select(ChatbotAction).where(
            ChatbotAction.workspace_id == workspace_id,
            ChatbotAction.chatbot_id == chatbot_id,
            ChatbotAction.is_enabled == True,  # noqa: E712
        )
    )
    return list(result.scalars().all())


async def get_action(
    db: AsyncSession,
    action_id: uuid.UUID,
    workspace_id: uuid.UUID,
) -> ChatbotAction | None:
    result = await db.execute(
        select(ChatbotAction).where(
            ChatbotAction.id == action_id,
            ChatbotAction.workspace_id == workspace_id,
        )
    )
    return result.scalar_one_or_none()


async def create_action(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    chatbot_id: uuid.UUID,
    action_type: str,
    name: str,
    trigger_description: str,
    config: dict,
    is_enabled: bool = True,
    parameters: list[dict] | None = None,
) -> ChatbotAction:
    action = ChatbotAction(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        chatbot_id=chatbot_id,
        action_type=action_type,
        name=name,
        trigger_description=trigger_description,
        config=config,
        is_enabled=is_enabled,
        parameters=parameters or [],
    )
    db.add(action)
    await db.flush()
    return action


async def update_action(
    db: AsyncSession,
    action_id: uuid.UUID,
    workspace_id: uuid.UUID,
    data: dict,
) -> ChatbotAction | None:
    action = await get_action(db, action_id, workspace_id)
    if not action:
        return None
    for key, value in data.items():
        setattr(action, key, value)
    await db.flush()
    return action


async def delete_action(
    db: AsyncSession,
    action_id: uuid.UUID,
    workspace_id: uuid.UUID,
) -> bool:
    action = await get_action(db, action_id, workspace_id)
    if not action:
        return False
    await db.delete(action)
    await db.flush()
    return True
