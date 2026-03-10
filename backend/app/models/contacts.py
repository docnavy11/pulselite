import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, TimestampUpdateMixin, UUIDPrimaryKeyMixin


class Company(UUIDPrimaryKeyMixin, TimestampUpdateMixin, Base):
    __tablename__ = "companies"

    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str | None] = mapped_column(Text, nullable=True)
    industry: Mapped[str | None] = mapped_column(Text, nullable=True)
    company_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    monthly_spend: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    intercom_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    custom_attributes: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))

    contacts: Mapped[list["Contact"]] = relationship(back_populates="company")


class Contact(UUIDPrimaryKeyMixin, TimestampUpdateMixin, Base):
    __tablename__ = "contacts"
    __table_args__ = (
        UniqueConstraint("workspace_id", "email"),
        UniqueConstraint("workspace_id", "intercom_id"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact_type: Mapped[str] = mapped_column(Text, server_default=text("'visitor'"))
    lifecycle_stage: Mapped[str] = mapped_column(Text, server_default=text("'unknown'"))
    intercom_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    crm_contact_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    company_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    browser: Mapped[str | None] = mapped_column(Text, nullable=True)
    os: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    signed_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_contacted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lead_score: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    lead_tier: Mapped[str | None] = mapped_column(Text, nullable=True)
    churn_risk: Mapped[str | None] = mapped_column(Text, nullable=True)
    expansion_potential: Mapped[str | None] = mapped_column(Text, nullable=True)
    custom_attributes: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))

    company: Mapped["Company | None"] = relationship(back_populates="contacts")
    events: Mapped[list["ContactEvent"]] = relationship(back_populates="contact")


class ContactEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "contact_events"

    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    contact_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=False)
    event_name: Mapped[str] = mapped_column(Text, nullable=False)
    event_metadata: Mapped[dict] = mapped_column("metadata", JSONB, server_default=text("'{}'::jsonb"))

    contact: Mapped["Contact"] = relationship(back_populates="events")


class DataAttribute(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "data_attributes"
    __table_args__ = (UniqueConstraint("workspace_id", "model", "name"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_type: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    options: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    archived: Mapped[bool] = mapped_column(server_default=text("FALSE"))


class Segment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "segments"

    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    filter_rules: Mapped[dict] = mapped_column(JSONB, nullable=False)
    person_type: Mapped[str] = mapped_column(Text, server_default=text("'contact'"))
