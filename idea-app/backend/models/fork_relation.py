from __future__ import annotations
from typing import Optional
from sqlalchemy import String, ForeignKey, CheckConstraint, Uuid, JSON
from sqlalchemy.orm import Mapped, mapped_column
import uuid

from .base import Base, TimestampMixin


class ForkRelation(Base, TimestampMixin):
    __tablename__ = "fork_relations"
    __table_args__ = (
        CheckConstraint(
            "relation_type IN ('fork','merge','evolve')", name="ck_fork_relation_type"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    child_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ideas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ideas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    relation_type: Mapped[str] = mapped_column(String(10), nullable=False)
    angle: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    # Immutable rights/attribution snapshot from the source Idea at derivation time.
    license_snapshot: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)
