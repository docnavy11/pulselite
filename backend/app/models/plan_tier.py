from sqlalchemy import BigInteger, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class PlanTier(TimestampMixin, Base):
    __tablename__ = "plan_tiers"

    slug: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    price_monthly_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_chatbots: Mapped[int] = mapped_column(Integer, nullable=False, default=-1)
    max_conversations_monthly: Mapped[int] = mapped_column(Integer, nullable=False, default=-1)
    max_knowledge_bases: Mapped[int] = mapped_column(Integer, nullable=False, default=-1)
    max_chars_indexed: Mapped[int] = mapped_column(BigInteger, nullable=False, default=-1)
    features: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
