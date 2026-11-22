"""Centralized Idea access and derivative authorization rules."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Idea, IdeaAccessGrant, User, ForkRelation


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


async def get_inherited_rights_chain(
    db: AsyncSession,
    idea: Idea,
    _visited: set[uuid.UUID] | None = None,
) -> list[dict]:
    """Return immutable ancestor license obligations, flattened and deduplicated.

    New edges carry a complete rights_chain. For older edges, reconstruct the
    ancestors from the still-existing parent graph and use the edge's own direct
    snapshot for the parent terms captured at derivation time.
    """
    visited = set(_visited or ())
    if idea.id in visited:
        raise ValueError("derivation lineage cycle detected")
    visited.add(idea.id)

    result = await db.execute(
        select(ForkRelation.license_snapshot, ForkRelation.parent_id).where(
            ForkRelation.child_id == idea.id
        )
    )
    by_source: dict[str, dict] = {}
    for snapshot, parent_id in result.all():
        if not snapshot:
            continue
        chain = snapshot.get("rights_chain")
        if isinstance(chain, list):
            edge_chain = chain
        else:
            edge_chain = []
            parent = await db.get(Idea, parent_id)
            if parent is not None and parent.id not in visited:
                edge_chain.extend(
                    await get_inherited_rights_chain(db, parent, visited)
                )
            edge_chain.append({
                "source_idea_id": snapshot.get("source_idea_id") or str(parent_id),
                "source_author_id": snapshot.get("source_author_id"),
                "source_author_name": snapshot.get("source_author_name", "匿名"),
                "license_code": snapshot.get("license_code"),
                "license_text_snapshot": snapshot.get("license_text_snapshot"),
                "license_version": snapshot.get("license_version"),
                "allow_fork": snapshot.get("allow_fork", False),
            })
        for item in edge_chain:
            source_id = str(item.get("source_idea_id") or "")
            key = source_id or (
                str(item.get("source_author_id") or "unknown")
                + ":"
                + str(item.get("license_code") or "unknown")
                + ":"
                + str(item.get("license_version") or "unknown")
            )
            by_source.setdefault(key, dict(item))
    return list(by_source.values())

async def get_effective_rights_chain(
    db: AsyncSession, idea: Idea
) -> list[dict]:
    """Ancestor obligations plus the current source's own published license."""
    ancestors = await get_inherited_rights_chain(db, idea)
    own = {
        "source_idea_id": str(idea.id),
        "source_author_id": str(idea.author_id) if idea.author_id else None,
        "source_author_name": None,
        "license_code": idea.license_code,
        "license_text_snapshot": idea.license_text_snapshot,
        "license_version": idea.license_version,
        "allow_fork": bool(idea.allow_fork),
    }
    if idea.author_id is not None:
        own["source_author_name"] = await db.scalar(
            select(User.username).where(User.id == idea.author_id)
        ) or "匿名"
    return ancestors + [own]


async def can_derive_from_idea(
    db: AsyncSession,
    idea: Idea,
    user_id: uuid.UUID | None,
) -> bool:
    """Require every upstream license in the immutable lineage to permit adaptation."""
    if not is_public_idea(idea):
        return False
    if not await can_view_idea(db, idea, user_id):
        return False
    if idea.legacy_license_review_status in ("pending", "expired"):
        return False
    if not idea.allow_fork:
        return False
    chain = await get_effective_rights_chain(db, idea)
    return bool(chain) and all(
        item.get("allow_fork") is True
        and item.get("license_code") in ("attribution_adaptation", "custom")
        for item in chain
    )


async def requires_custom_license_confirmation(
    db: AsyncSession, ideas: list[Idea]
) -> bool:
    for idea in ideas:
        chain = await get_effective_rights_chain(db, idea)
        if any(item.get("license_code") == "custom" for item in chain):
            return True
    return False


async def can_manage_idea(idea: Idea, user_id: uuid.UUID | None) -> bool:
    return user_id is not None and idea.author_id == user_id



async def build_derivation_snapshot(
    db: AsyncSession,
    idea: Idea,
    *,
    custom_license_acknowledged: bool = False,
    acknowledged_by: uuid.UUID | None = None,
) -> dict:
    """Freeze the source terms and every inherited upstream obligation."""
    chain = await get_effective_rights_chain(db, idea)
    custom_required = any(item.get("license_code") == "custom" for item in chain)
    return {
        "source_idea_id": str(idea.id),
        "source_author_id": str(idea.author_id) if idea.author_id else None,
        "source_author_name": next(
            (item.get("source_author_name") for item in reversed(chain)
             if item.get("source_idea_id") == str(idea.id)),
            "匿名",
        ),
        "license_code": idea.license_code,
        "license_text_snapshot": idea.license_text_snapshot,
        "license_version": idea.license_version,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "allow_fork": bool(idea.allow_fork),
        "rights_chain": chain,
        "effective_allow_fork": bool(chain) and all(
            item.get("allow_fork") is True
            and item.get("license_code") in ("attribution_adaptation", "custom")
            for item in chain
        ),
        "custom_license_confirmation_required": custom_required,
        "custom_license_acknowledgement": {
            "acknowledged": bool(custom_required and custom_license_acknowledged),
            "acknowledged_by": str(acknowledged_by) if acknowledged_by else None,
            "acknowledged_at": datetime.now(timezone.utc).isoformat()
                if custom_required and custom_license_acknowledged else None,
        },
    }
