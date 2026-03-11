import uuid
from datetime import datetime

from pydantic import BaseModel


class GapClusterResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    chatbot_id: uuid.UUID | None
    topic_label: str
    topic_keywords: list[str] | None
    gap_count: int
    representative_query: str | None
    status: str
    resolved_at: datetime | None
    clustered_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class GapClusterDetailResponse(GapClusterResponse):
    example_queries: list[str]
    draft_article_title: str | None = None
    draft_article_body: str | None = None


class GapClusterArticleUpdate(BaseModel):
    title: str | None = None
    body: str | None = None
