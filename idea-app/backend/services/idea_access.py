"""Centralized Idea access and derivative authorization rules."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Idea, IdeaAccessGrant


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
