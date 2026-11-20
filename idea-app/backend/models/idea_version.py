from __future__ import annotations

from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy import (
    String, Text, DateTime, ForeignKey, CheckConstraint, Uuid,
    UniqueConstraint, Index,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class IdeaVersion(Base, TimestampMixin):
    """Immutable published snapshot or editable author-owned draft."""

    __tablename__ = "idea_versions"
    __table_args__ = (
        UniqueConstraint("idea_id", "version_number", name="uq_idea_versions_number"),
        CheckConstraint("version_number > 0", name="ck_idea_versions_number_positive"),
        CheckConstraint("status IN ('draft','published')", name="ck_idea_versions_status"),
        Index("idx_idea_versions_idea_status_number", "idea_id", "status", "version_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    idea_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("ideas.id", ondelete="CASCADE"), nullable=False)
    version_number: Mapped[int] = mapped_column(nullable=False)
    content_snapshot: Mapped[str] = mapped_column(String(300), nullable=False)
    change_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft", server_default="draft")
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    published_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class IdeaVersionContribution(Base):
    """Frozen attribution for a contribution consumed by a version."""

    __tablename__ = "idea_version_contributions"
    __table_args__ = (
        UniqueConstraint("contribution_id", name="uq_version_contribution_consumed_once"),
        UniqueConstraint("version_id", "contribution_id", name="uq_version_contribution_pair"),
        Index("idx_idea_version_contributions_version", "version_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    version_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("idea_versions.id", ondelete="CASCADE"), nullable=False)
    contribution_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("idea_contributions.id", ondelete="RESTRICT"), nullable=False)
    author_id_snapshot: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    author_name_snapshot: Mapped[str] = mapped_column(String(80), nullable=False)
    content_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
