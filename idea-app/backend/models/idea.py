from __future__ import annotations

from datetime import datetime
from typing import Optional
from sqlalchemy import String, Boolean, Integer, DateTime, ForeignKey, Text, func, CheckConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column
import uuid

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
    last_fork_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_touch_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=func.now()
    )
