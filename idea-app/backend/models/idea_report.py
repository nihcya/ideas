from __future__ import annotations

from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy import String, Text, DateTime, ForeignKey, CheckConstraint, Uuid, func, Index, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class IdeaReport(Base, TimestampMixin):
    __tablename__ = "idea_reports"
    __table_args__ = (
        CheckConstraint(
            "reason IN ('spam','harassment','copyright','privacy','misinformation','other')",
            name="ck_idea_reports_reason",
        ),
        CheckConstraint(
            "status IN ('pending','in_review','resolved','dismissed')",
            name="ck_idea_reports_status",
        ),
        Index("idx_idea_reports_status_created", "status", "created_at"),
        Index("idx_idea_reports_idea_status", "idea_id", "status"),
        Index(
            "uq_idea_reports_open_per_reporter",
            "idea_id", "reporter_id", unique=True,
            postgresql_where=text("status IN ('pending', 'in_review')"),
            sqlite_where=text("status IN ('pending', 'in_review')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    idea_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ideas.id", ondelete="CASCADE"), nullable=False
    )
    reporter_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    reason: Mapped[str] = mapped_column(String(24), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", server_default="pending")
    reviewed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_note: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    action_taken: Mapped[str] = mapped_column(String(24), nullable=False, default="none", server_default="none")
