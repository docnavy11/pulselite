import asyncio
import logging
import uuid

from sqlalchemy import select

from app.database import async_session_factory
from app.models.intelligence import GapCluster, GapEvent
from app.models.knowledge import Article, KnowledgeBase
from app.services.llm import get_llm_client
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task
def auto_draft_articles(workspace_id: str) -> dict:
    return asyncio.run(_draft(uuid.UUID(workspace_id)))


async def _draft(workspace_id: uuid.UUID) -> dict:
    async with async_session_factory() as session:
        try:
            result = await session.execute(
                select(GapCluster).where(
                    GapCluster.workspace_id == workspace_id,
                    GapCluster.status == "open",
                    GapCluster.gap_count >= 3,
                    GapCluster.draft_article_id.is_(None),
                )
            )
            clusters = list(result.scalars().all())

            drafted = 0
            for cluster in clusters:
                success = await _draft_for_cluster(session, cluster)
                if success:
                    drafted += 1

            await session.commit()
            return {"status": "success", "drafted": drafted}
        except Exception:
            await session.rollback()
            raise


async def _draft_for_cluster(session, cluster: GapCluster) -> bool:
    result = await session.execute(select(GapEvent.query).where(GapEvent.gap_cluster_id == cluster.id).limit(20))
    queries = [row[0] for row in result.all()]

    if not queries:
        return False

    queries_text = "\n".join(f"- {q}" for q in queries)
    prompt = (
        "Draft a help article that answers these common customer questions:\n\n"
        f"{queries_text}\n\n"
        "Write the article in Markdown format with:\n"
        "1. A clear, descriptive title (first line as # heading)\n"
        "2. A brief introduction\n"
        "3. Step-by-step answers or explanations\n"
        "4. Keep it concise and actionable\n\n"
        "Output ONLY the article content in Markdown."
    )

    try:
        client = get_llm_client("openai")
        response = await client.generate(
            messages=[
                {"role": "system", "content": "You are a technical writer creating help center articles."},
                {"role": "user", "content": prompt},
            ],
            model="gpt-4o-mini",
            temperature=0.5,
            max_tokens=2000,
        )
    except Exception as e:
        logger.error(f"LLM draft failed for cluster {cluster.id}: {e}")
        return False

    content = response.strip()
    title = _extract_title(content)

    kb_id = await _get_default_kb(session, cluster)

    article = Article(
        workspace_id=cluster.workspace_id,
        knowledge_base_id=kb_id,
        title=title,
        body=content,
        state="ai_draft_pending",
        is_ai_drafted=True,
        gap_cluster_id=cluster.id,
    )
    session.add(article)
    await session.flush()

    cluster.draft_article_id = article.id
    cluster.status = "draft_ready"

    return True


def _extract_title(content: str) -> str:
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return "Untitled Draft Article"


async def _get_default_kb(session, cluster: GapCluster) -> uuid.UUID | None:
    if cluster.chatbot_id:
        result = await session.execute(
            select(KnowledgeBase.id).where(KnowledgeBase.chatbot_id == cluster.chatbot_id).limit(1)
        )
        row = result.first()
        if row:
            return row[0]

    result = await session.execute(
        select(KnowledgeBase.id).where(KnowledgeBase.workspace_id == cluster.workspace_id).limit(1)
    )
    row = result.first()
    return row[0] if row else None
