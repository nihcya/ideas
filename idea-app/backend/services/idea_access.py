"""Centralized Idea access and derivative authorization rules."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Idea, IdeaAccessGrant, User


def is_public_idea(idea: Idea) -> bool:
    return (
        idea.publication_status == "published"
        and idea.visibility == "public"
        and idea.status == "active"
    )


async def can_view_idea(
    db: AsyncSession,
    idea: Idea,
    user_id: uuid.UUID | None,
) -> bool:
    """Return whether a user may read an Idea. Pending invites grant no access."""
    if idea.status == "rejected":
        return False
    if is_public_idea(idea):
        return True
    if user_id is None:
        return False
    if idea.author_id == user_id:
        return True

    result = await db.execute(
        select(IdeaAccessGrant.id).where(
            IdeaAccessGrant.idea_id == idea.id,
            IdeaAccessGrant.user_id == user_id,
            IdeaAccessGrant.status == "accepted",
        ).limit(1)
    )
    return result.scalar_one_or_none() is not None


async def can_derive_from_idea(
    db: AsyncSession,
    idea: Idea,
    user_id: uuid.UUID | None,
) -> bool:
    """Only explicitly licensed public Ideas may be used as derivative sources."""
    # Derivative operations are intentionally limited to published public Ideas.
    # An accepted private invitation grants read access only; contributor work is
    # handled by the collaboration workflow and does not imply Fork/Collide/Evolve rights.
    if not is_public_idea(idea):
        return False
    if not await can_view_idea(db, idea, user_id):
        return False
    if idea.legacy_license_review_status in ("pending", "expired"):
        return False
    if not idea.allow_fork:
        return False
    return idea.license_code in ("attribution_adaptation", "custom")


async def can_manage_idea(idea: Idea, user_id: uuid.UUID | None) -> bool:
    return user_id is not None and idea.author_id == user_id



async def build_derivation_snapshot(db: AsyncSession, idea: Idea) -> dict:
    """Freeze source identity and license terms when a derivative edge is created."""
    author_name = None
    if idea.author_id is not None:
        author_name = await db.scalar(
            select(User.username).where(User.id == idea.author_id)
        )
    return {
        "source_idea_id": str(idea.id),
        "source_author_id": str(idea.author_id) if idea.author_id else None,
        "source_author_name": author_name or "匿名",
        "license_code": idea.license_code,
        "license_text_snapshot": idea.license_text_snapshot,
        "license_version": idea.license_version,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "allow_fork": idea.allow_fork,
    }
