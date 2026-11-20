from __future__ import annotations

from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy import String, Text, DateTime, ForeignKey, CheckConstraint, Uuid, func, Index
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class IdeaContribution(Base, TimestampMixin):
    """An immutable-at-review proposal submitted by an accepted Idea contributor."""

    __tablename__ = "idea_contributions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('submitted','accepted','rejected','withdrawn')",
            name="ck_idea_contributions_status",
        ),
        Index("idx_idea_contributions_idea_status_created", "idea_id", "status", "created_at"),
        Index("idx_idea_contributions_author_status", "author_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    idea_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ideas.id", ondelete="CASCADE"), nullable=False
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="submitted", server_default="submitted"
    )
    reviewed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
