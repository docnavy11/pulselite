"""Factories for chatbot, knowledge base, and document models."""
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.organizational import Workspace
from app.models.knowledge import Chatbot, KnowledgeBase, Document


async def make_chatbot(
    db: AsyncSession,
    workspace: Workspace,
    *,
    name: str = "Test Bot",
    llm_provider: str = "openai",
    llm_model: str = "gpt-4o-mini",
    confidence_threshold: float = 0.7,
) -> Chatbot:
    bot = Chatbot(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        name=name,
        llm_provider=llm_provider,
        llm_model=llm_model,
        confidence_threshold=confidence_threshold,
    )
    db.add(bot)
    await db.flush()
    return bot


async def make_knowledge_base(
    db: AsyncSession,
    workspace: Workspace,
    chatbot: Chatbot,
    *,
    name: str = "Test KB",
    kb_type: str = "general",
) -> KnowledgeBase:
    kb = KnowledgeBase(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        chatbot_id=chatbot.id,
        name=name,
        kb_type=kb_type,
    )
    db.add(kb)
    await db.flush()
    return kb


async def make_document(
    db: AsyncSession,
    workspace: Workspace,
    knowledge_base: KnowledgeBase,
    *,
    title: str = "Test Document",
    source_type: str = "text",
    raw_content: str = "This is test content for the document.",
    status: str = "indexed",
) -> Document:
    doc = Document(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        knowledge_base_id=knowledge_base.id,
        title=title,
        source_type=source_type,
        raw_content=raw_content,
        status=status,
    )
    db.add(doc)
    await db.flush()
    return doc
