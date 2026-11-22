"""Regression tests for immutable source attribution and derivation contracts."""

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from models import User, Idea, ForkRelation
from routers import ideas as ideas_router
from routers import evolve as evolve_router
from schemas.idea import IdeaForkRequest, CollideConfirmRequest


async def _public_source(db, username="derivation_owner"):
    owner = User(username=username, password_hash="test-hash", bio="")
    db.add(owner)
    await db.flush()
    idea = Idea(
        content="一个公开且允许衍生的原始创意",
        color_hex="#123456",
        source="ugc",
        author_id=owner.id,
        border_style="gold-thin",
        publication_status="published",
        visibility="public",
        license_code="attribution_adaptation",
        license_text_snapshot=None,
        license_version="v1",
        allow_fork=True,
        is_forkable=True,
        legacy_license_review_status="confirmed",
    )
    db.add(idea)
    await db.commit()
    return owner, idea


@pytest.mark.asyncio
async def test_derivative_keeps_source_attribution_after_source_is_unpublished(
    db_session, monkeypatch
):
    owner, source = await _public_source(db_session)
    derivative_author = User(
        username="derivation_child_author", password_hash="test-hash", bio=""
    )
    db_session.add(derivative_author)
    await db_session.commit()

    async def allow_audit(*args, **kwargs):
        return True, ""

    async def noop(*args, **kwargs):
        return None

    monkeypatch.setattr(ideas_router, "audit_content", allow_audit)
    monkeypatch.setattr(ideas_router.cache, "delete_pattern", noop)
    monkeypatch.setattr(ideas_router.cache, "delete", noop)

    forked = await ideas_router.fork_idea(
        IdeaForkRequest(parent_id=str(source.id), content="基于原始创意形成的衍生方案"),
        db_session,
        derivative_author,
    )
    relation_result = await db_session.execute(
        select(ForkRelation).where(ForkRelation.child_id == uuid.UUID(forked.id))
    )
    relation = relation_result.scalar_one()
    assert relation.license_snapshot["source_author_name"] == owner.username
    assert relation.license_snapshot["license_code"] == "attribution_adaptation"

    await ideas_router.unpublish_idea(source.id, db_session, owner)
    detail = await ideas_router.get_idea_detail(
        uuid.UUID(forked.id), db_session, derivative_author
    )

    assert len(detail.lineage.parents) == 1
    assert detail.lineage.parents[0].id.startswith("withdrawn:")
    assert detail.lineage.parents[0].id != str(source.id)
    assert detail.lineage.parents[0].is_navigable is False
    assert detail.lineage.parents[0].author == owner.username
    assert detail.lineage.parents[0].title == "已撤回的来源创意"
    assert detail.lineage.parents[0].license_snapshot["license_code"] == "attribution_adaptation"


@pytest.mark.asyncio
async def test_collide_confirm_rejects_same_source_twice(db_session):
    owner, source = await _public_source(db_session, "collide_duplicate_owner")
    with pytest.raises(HTTPException) as exc:
        await evolve_router.collide_confirm(
            CollideConfirmRequest(
                idea_a_id=str(source.id),
                idea_b_id=str(source.id),
                content="不能把同一个创意碰撞两次",
                ai_assisted=False,
            ),
            db_session,
            owner,
        )
    assert exc.value.status_code == 422
    assert exc.value.detail["error"]["code"] == "DUPLICATE_SOURCE"
