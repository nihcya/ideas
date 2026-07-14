from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Boolean, DateTime, ForeignKey, func, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column
import uuid

from .base import Base, TimestampMixin


class VaultItem(Base, TimestampMixin):
    __tablename__ = "vault_items"
    __table_args__ = (UniqueConstraint("user_id", "idea_id", name="uq_vault_user_idea"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    idea_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ideas.id", ondelete="CASCADE"), nullable=False
    )
    is_producer: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    last_touch_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=func.now(), index=True
    )
