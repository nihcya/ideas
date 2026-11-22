from __future__ import annotations

from typing import Optional
import uuid

from sqlalchemy import (
    String, Text, ForeignKey, UniqueConstraint, CheckConstraint,
    Uuid, Index,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class IdeaAssociation(Base, TimestampMixin):
    """Non-lineage relationship between Ideas, e.g. 'inspired by'.

    This table is intentionally separate from ForkRelation: associations never
    inherit licenses and never grant derivative rights.
    """

    __tablename__ = "idea_associations"
    __table_args__ = (
        UniqueConstraint("source_idea_id", "target_idea_id", name="uq_idea_association_pair"),
        CheckConstraint("source_idea_id <> target_idea_id", name="ck_idea_association_no_self"),
        CheckConstraint("relation_type = 'inspired'", name="ck_idea_association_type"),
        Index("idx_idea_associations_source", "source_idea_id", "created_at"),
        Index("idx_idea_associations_target", "target_idea_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_idea_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ideas.id", ondelete="CASCADE"), nullable=False
    )
    target_idea_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ideas.id", ondelete="CASCADE"), nullable=False
    )
    relation_type: Mapped[str] = mapped_column(String(16), nullable=False, default="inspired", server_default="inspired")
    created_by: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
