from __future__ import annotations

from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy import (
    String, Text, DateTime, ForeignKey, UniqueConstraint, CheckConstraint,
    Uuid, JSON, Integer, func, Index,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class Collaboration(Base, TimestampMixin):
    """A first-class asynchronous workspace that can combine multiple Ideas."""

    __tablename__ = "collaborations"
    __table_args__ = (
        CheckConstraint("status IN ('draft','published','archived')", name="ck_collaborations_status"),
        CheckConstraint("visibility IN ('private','public')", name="ck_collaborations_visibility"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft", server_default="draft")
    visibility: Mapped[str] = mapped_column(String(16), nullable=False, default="private", server_default="private")
    published_idea_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, ForeignKey("ideas.id", ondelete="SET NULL"), nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class CollaborationMember(Base, TimestampMixin):
    __tablename__ = "collaboration_members"
    __table_args__ = (
        UniqueConstraint("collaboration_id", "user_id", name="uq_collaboration_member_user"),
        CheckConstraint("role IN ('owner','contributor','viewer')", name="ck_collaboration_member_role"),
        CheckConstraint("status IN ('pending','accepted','declined','revoked')", name="ck_collaboration_member_status"),
        Index("idx_collaboration_members_user_status", "user_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    collaboration_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("collaborations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", server_default="pending")
    invited_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    invited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    responded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class CollaborationSource(Base, TimestampMixin):
    __tablename__ = "collaboration_sources"
    __table_args__ = (
        UniqueConstraint("collaboration_id", "idea_id", name="uq_collaboration_source_idea"),
        Index("idx_collaboration_sources_collaboration", "collaboration_id", "position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    collaboration_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("collaborations.id", ondelete="CASCADE"), nullable=False, index=True)
    idea_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("ideas.id", ondelete="RESTRICT"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rights_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)


class CollaborationContribution(Base, TimestampMixin):
    __tablename__ = "collaboration_contributions"
    __table_args__ = (
        CheckConstraint("status IN ('submitted','accepted','rejected','withdrawn')", name="ck_collaboration_contribution_status"),
        CheckConstraint("contribution_type IN ('idea','revision','comment','research')", name="ck_collaboration_contribution_type"),
        Index("idx_collab_contributions_workspace_status", "collaboration_id", "status", "created_at"),
        Index("idx_collab_contributions_author", "author_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    collaboration_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("collaborations.id", ondelete="CASCADE"), nullable=False, index=True)
    author_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    source_idea_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, ForeignKey("ideas.id", ondelete="SET NULL"), nullable=True)
    contribution_type: Mapped[str] = mapped_column(String(16), nullable=False, default="idea", server_default="idea")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="submitted", server_default="submitted")
    reviewed_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class CollaborationEvent(Base, TimestampMixin):
    __tablename__ = "collaboration_events"
    __table_args__ = (Index("idx_collaboration_events_timeline", "collaboration_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    collaboration_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("collaborations.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
