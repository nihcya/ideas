from __future__ import annotations

from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy import String, DateTime, ForeignKey, UniqueConstraint, CheckConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class IdeaAccessGrant(Base, TimestampMixin):
    """Direct per-Idea access invitation. Pending grants never authorize reads."""

    __tablename__ = "idea_access_grants"
    __table_args__ = (
        UniqueConstraint("idea_id", "user_id", name="uq_idea_access_grant_idea_user"),
        CheckConstraint("role IN ('contributor','viewer')", name="ck_idea_access_grant_role"),
        CheckConstraint(
            "status IN ('pending','accepted','declined','revoked')",
            name="ck_idea_access_grant_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    idea_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ideas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="viewer", server_default="viewer")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", server_default="pending")
    invited_by: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    invited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    responded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
