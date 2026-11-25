from __future__ import annotations

from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy import (
    String, Boolean, Integer, DateTime, ForeignKey, func, CheckConstraint,
    Uuid, Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class Idea(Base, TimestampMixin):
    __tablename__ = "ideas"
    __table_args__ = (
        CheckConstraint(
            "source IN ('ugc','pgc','today_spark','fork','merge','evolve')",
            name="ck_ideas_source",
        ),
        CheckConstraint("border_style IN ('gold-thin','none')", name="ck_ideas_border"),
        CheckConstraint("status IN ('active','fading','faded','rejected')", name="ck_ideas_status"),
        CheckConstraint(
            "publication_status IN ('draft','published','archived')",
            name="ck_ideas_publication_status",
        ),
        CheckConstraint("visibility IN ('private','public')", name="ck_ideas_visibility"),
        CheckConstraint(
            "legacy_license_review_status IN ('not_required','pending','confirmed','expired')",
            name="ck_ideas_legacy_license_review_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    content: Mapped[str] = mapped_column(String(300), nullable=False)
    color_hex: Mapped[str] = mapped_column(String(7), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    author_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    border_style: Mapped[str] = mapped_column(String(10), default="none", server_default="none")
    fork_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    is_forkable: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    ai_assisted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    evolved_from: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(10), default="active", server_default="active")

    # V2 publication and rights are separate from the existing content moderation/fade status.
    publication_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="draft", server_default="draft", index=True
    )
    visibility: Mapped[str] = mapped_column(
        String(16), nullable=False, default="private", server_default="private", index=True
    )
    license_code: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    license_text_snapshot: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    license_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    allow_fork: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    legacy_license_review_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="not_required", server_default="not_required", index=True
    )
    legacy_license_review_due_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    legacy_license_review_notified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    legacy_license_reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    last_fork_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_touch_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=func.now()
    )
