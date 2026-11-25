from __future__ import annotations

from typing import Optional
from sqlalchemy import String, Boolean, ForeignKey, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column
import uuid

from .base import Base, TimestampMixin


class Notification(Base, TimestampMixin):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(40), nullable=False)
    content: Mapped[str] = mapped_column(String(200), nullable=False)
    idea_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("ideas.id", ondelete="SET NULL"), nullable=True
    )
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    collaboration_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("collaborations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    read: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    idea_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("ideas.id", ondelete="SET NULL"), nullable=True
    )
    content_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    result: Mapped[str] = mapped_column(String(10), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    auditor: Mapped[str] = mapped_column(String(10), nullable=False)


class BannedWord(Base):
    __tablename__ = "banned_words"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    word: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    level: Mapped[str] = mapped_column(String(10), default="high", server_default="high")
