"""Bounded Idea Universe graph and non-lineage Inspired associations."""
from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from deps import get_db, get_current_user, get_optional_user
from models import Idea, User, ForkRelation, IdeaAssociation, IdeaAccessGrant
from schemas.idea_association import IdeaAssociationCreate
from services.idea_access import can_view_idea

router = APIRouter(prefix="/ideas", tags=["universe"])

_PRIVATE_SNAPSHOT_KEYS = {
    "idea_id", "source_idea_id", "source_author_id", "author_id",
    "parent_idea_id", "child_idea_id",
}


def _sanitize_snapshot(value):
    if isinstance(value, dict):
        return {
            key: _sanitize_snapshot(item)
            for key, item in value.items()
            if key not in _PRIVATE_SNAPSHOT_KEYS
        }
    if isinstance(value, list):
        return [_sanitize_snapshot(item) for item in value]
    return value


def _not_found():
    return HTTPException(
        status_code=404,
        detail={"error": {"code": "NOT_FOUND", "message": "点子不存在"}},
    )


async def _visible_idea_ids(
    db: AsyncSession,
    idea_ids: set[uuid.UUID],
    viewer_id: uuid.UUID | None,
) -> set[uuid.UUID]:
    """Batch-check graph node visibility to avoid one ACL query per node."""
    if not idea_ids:
        return set()
    visible_predicates = [
        and_(
            Idea.publication_status == "published",
            Idea.visibility == "public",
            Idea.status == "active",
        )
    ]
    grant_join = False
    if viewer_id is not None:
        visible_predicates.extend([
            Idea.author_id == viewer_id,
            IdeaAccessGrant.id.is_not(None),
        ])
        grant_join = True
    query = select(Idea.id).where(
        Idea.id.in_(idea_ids),
        Idea.status != "rejected",
        or_(*visible_predicates),
    )
    if grant_join:
        query = query.outerjoin(
            IdeaAccessGrant,
            and_(
                IdeaAccessGrant.idea_id == Idea.id,
                IdeaAccessGrant.user_id == viewer_id,
                IdeaAccessGrant.status == "accepted",
            ),
        )
    result = await db.execute(query.distinct())
    return set(result.scalars().all())


def _node(idea: Idea, author: str, depth: int):
    return {
        "id": str(idea.id),
        "title": idea.content[:60],
        "color_hex": idea.color_hex,
        "author": author or "匿名",
        "depth": depth,
        "node_type": "idea",
        "navigable": True,
        "is_root": False,
    }


@router.get("/{idea_id}/graph")
async def get_idea_graph(
    idea_id: uuid.UUID,
    depth: int = Query(2, ge=1, le=3),
    direction: Literal["ancestors", "descendants", "both"] = Query("both"),
    include_inspired: bool = Query(True),
    max_nodes: int = Query(100, ge=10, le=100),
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    viewer_id = user.id if user else None
    root = await db.get(Idea, idea_id)
    if root is None or not await can_view_idea(db, root, viewer_id):
        raise _not_found()
    root_author = await db.scalar(select(User.username).where(User.id == root.author_id)) if root.author_id else "匿名"

    nodes = {
        str(root.id): {
            **_node(root, root_author or "匿名", 0),
            "is_root": True,
        }
    }
    edges = []
    edge_keys = set()
    visited = {root.id}
    frontier = {root.id}
    truncated = False
    max_edges = 300

    for level in range(1, depth + 1):
        if not frontier or truncated:
            break
        candidates = []
        neighbor_ids = set()

        if direction in ("ancestors", "both"):
            rows = (await db.execute(
                select(ForkRelation).where(ForkRelation.child_id.in_(frontier))
            )).scalars().all()
            for relation in rows:
                candidates.append({
                    "kind": "lineage",
                    "direction": "ancestor",
                    "id": relation.id,
                    "neighbor_id": relation.parent_id,
                    "current_id": relation.child_id,
                    "source_id": relation.parent_id,
                    "target_id": relation.child_id,
                    "relation_type": relation.relation_type,
                    "license_snapshot": relation.license_snapshot,
                })
                neighbor_ids.add(relation.parent_id)

            if include_inspired:
                associations = (await db.execute(
                    select(IdeaAssociation).where(IdeaAssociation.target_idea_id.in_(frontier))
                )).scalars().all()
                for association in associations:
                    candidates.append({
                        "kind": "inspired",
                        "direction": "ancestor",
                        "id": association.id,
                        "neighbor_id": association.source_idea_id,
                        "current_id": association.target_idea_id,
                        "source_id": association.source_idea_id,
                        "target_id": association.target_idea_id,
                        "relation_type": "inspired",
                        "note": association.note,
                    })
                    neighbor_ids.add(association.source_idea_id)

        if direction in ("descendants", "both"):
            rows = (await db.execute(
                select(ForkRelation).where(ForkRelation.parent_id.in_(frontier))
            )).scalars().all()
            for relation in rows:
                candidates.append({
                    "kind": "lineage",
                    "direction": "descendant",
                    "id": relation.id,
                    "neighbor_id": relation.child_id,
                    "current_id": relation.parent_id,
                    "source_id": relation.parent_id,
                    "target_id": relation.child_id,
                    "relation_type": relation.relation_type,
                    "license_snapshot": relation.license_snapshot,
                })
                neighbor_ids.add(relation.child_id)

            if include_inspired:
                associations = (await db.execute(
                    select(IdeaAssociation).where(IdeaAssociation.source_idea_id.in_(frontier))
                )).scalars().all()
                for association in associations:
                    candidates.append({
                        "kind": "inspired",
                        "direction": "descendant",
                        "id": association.id,
                        "neighbor_id": association.target_idea_id,
                        "current_id": association.source_idea_id,
                        "source_id": association.source_idea_id,
                        "target_id": association.target_idea_id,
                        "relation_type": "inspired",
                        "note": association.note,
                    })
                    neighbor_ids.add(association.target_idea_id)

        if not candidates:
            break

        neighbor_map = {}
        if neighbor_ids:
            neighbor_result = await db.execute(
                select(Idea, User.username)
                .outerjoin(User, User.id == Idea.author_id)
                .where(Idea.id.in_(neighbor_ids))
            )
            neighbor_map = {
                idea.id: (idea, author or "匿名")
                for idea, author in neighbor_result.all()
            }

        next_frontier = set()
        for candidate in candidates:
            neighbor_id = candidate["neighbor_id"]
            neighbor_pair = neighbor_map.get(neighbor_id)
            if neighbor_pair is None:
                continue
            neighbor, author = neighbor_pair
            visible = neighbor.id in visible_ids

            if not visible:
                # Only upstream lineage keeps an opaque, non-navigable attribution
                # placeholder. Private descendants and Inspired edges are omitted.
                if (
                    candidate["kind"] == "lineage"
                    and candidate["direction"] == "ancestor"
                    and candidate["license_snapshot"]
                ):
                    restricted_id = f"restricted:{candidate['id']}"
                    if restricted_id not in nodes:
                        if len(nodes) >= max_nodes:
                            truncated = True
                            continue
                        nodes[restricted_id] = {
                            "id": restricted_id,
                            "title": (
                                "已撤回的来源创意"
                                if neighbor.status != "active"
                                or neighbor.publication_status != "published"
                                else "受限来源创意"
                            ),
                            "color_hex": "#9CA3AF",
                            "author": (
                                (candidate["license_snapshot"] or {}).get("source_author_name")
                                or "匿名"
                            ),
                            "depth": level,
                            "node_type": "restricted",
                            "navigable": False,
                            "is_root": False,
                        }
                    source_key = restricted_id
                    target_key = str(candidate["target_id"])
                    edge_key = (str(candidate["id"]), source_key, target_key)
                    if edge_key not in edge_keys and len(edges) < max_edges:
                        edges.append({
                            "id": str(candidate["id"]),
                            "source": source_key,
                            "target": target_key,
                            "type": candidate["relation_type"],
                            "license_snapshot": _sanitize_snapshot(candidate["license_snapshot"]),
                        })
                        edge_keys.add(edge_key)
                    elif len(edges) >= max_edges:
                        truncated = True
                continue

            neighbor_key = str(neighbor.id)
            if neighbor_key not in nodes:
                if len(nodes) >= max_nodes:
                    truncated = True
                    continue
                nodes[neighbor_key] = _node(neighbor, author, level)
                if neighbor.id not in visited:
                    next_frontier.add(neighbor.id)
                    visited.add(neighbor.id)

            source_key = str(candidate["source_id"])
            target_key = str(candidate["target_id"])
            edge_key = (str(candidate["id"]), source_key, target_key)
            if edge_key in edge_keys:
                continue
            if len(edges) >= max_edges:
                truncated = True
                continue
            edge = {
                "id": str(candidate["id"]),
                "source": source_key,
                "target": target_key,
                "type": candidate["relation_type"],
            }
            if candidate["kind"] == "lineage":
                edge["license_snapshot"] = candidate["license_snapshot"]
            elif candidate.get("note"):
                edge["note"] = candidate["note"]
            edges.append(edge)
            edge_keys.add(edge_key)

        frontier = next_frontier

    return {
        "root_id": str(root.id),
        "depth": depth,
        "direction": direction,
        "include_inspired": include_inspired,
        "nodes": list(nodes.values()),
        "edges": edges,
        "truncated": truncated,
    }


@router.post("/{idea_id}/associations", status_code=201)
async def create_inspired_association(
    idea_id: uuid.UUID,
    payload: IdeaAssociationCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    target = await db.scalar(
        select(Idea).where(Idea.id == idea_id).with_for_update()
    )
    if target is None or target.author_id != user.id or target.status != "active":
        raise _not_found()
    if payload.source_idea_id == idea_id:
        raise HTTPException(
            status_code=422,
            detail={"error": {"code": "SELF_ASSOCIATION", "message": "不能将创意关联为自己的灵感来源"}},
        )
    source = await db.get(Idea, payload.source_idea_id)
    if source is None or not await can_view_idea(db, source, user.id):
        raise _not_found()
    existing = await db.scalar(select(IdeaAssociation).where(
        IdeaAssociation.source_idea_id == source.id,
        IdeaAssociation.target_idea_id == target.id,
    ))
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail={"error": {"code": "ASSOCIATION_EXISTS", "message": "该灵感关联已存在"}},
        )
    association = IdeaAssociation(
        source_idea_id=source.id,
        target_idea_id=target.id,
        relation_type="inspired",
        created_by=user.id,
        note=payload.note,
    )
    db.add(association)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail={"error": {"code": "ASSOCIATION_EXISTS", "message": "该灵感关联已存在"}},
        )
    return {
        "id": str(association.id),
        "source_idea_id": str(source.id),
        "target_idea_id": str(target.id),
        "relation_type": "inspired",
    }


@router.delete("/{idea_id}/associations/{association_id}")
async def delete_inspired_association(
    idea_id: uuid.UUID,
    association_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    target = await db.get(Idea, idea_id)
    if target is None or target.author_id != user.id:
        raise _not_found()
    association = await db.scalar(select(IdeaAssociation).where(
        IdeaAssociation.id == association_id,
        IdeaAssociation.target_idea_id == idea_id,
    ).with_for_update())
    if association is None:
        raise _not_found()
    await db.delete(association)
    await db.commit()
    return {"deleted": True}
