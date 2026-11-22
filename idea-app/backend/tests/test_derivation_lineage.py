"""Regression tests for immutable source attribution and derivation contracts."""

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from models import User, Idea, ForkRelation
from routers import ideas as ideas_router
from routers import evolve as evolve_router
from schemas.idea import IdeaForkRequest, CollideConfirmRequest, EvolveConfirmRequest, IdeaPublishRequest
from services.idea_access import get_effective_rights_chain


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


@pytest.mark.asyncio
async def test_custom_ancestor_requires_explicit_ack_and_is_frozen(db_session, monkeypatch):
    owner, source = await _public_source(db_session, "custom_rights_owner")
    source.license_code = "custom"
    source.license_text_snapshot = "必须保留署名，并在衍生发布时注明来源。"
    await db_session.commit()
    derivative_author = User(
        username="custom_rights_derivative", password_hash="test-hash", bio=""
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

    with pytest.raises(HTTPException) as exc:
        await ideas_router.fork_idea(
            IdeaForkRequest(
                parent_id=str(source.id),
                content="未确认自定义授权的衍生内容",
            ),
            db_session,
            derivative_author,
        )
    assert exc.value.status_code == 422
    assert exc.value.detail["error"]["code"] == "CUSTOM_LICENSE_CONFIRMATION_REQUIRED"

    forked = await ideas_router.fork_idea(
        IdeaForkRequest(
            parent_id=str(source.id),
            content="明确接受自定义授权后的衍生内容",
            confirm_custom_licenses=True,
        ),
        db_session,
        derivative_author,
    )
    relation = await db_session.scalar(
        select(ForkRelation).where(
            ForkRelation.child_id == uuid.UUID(forked.id)
        )
    )
    assert relation.license_snapshot["rights_chain"][0]["license_code"] == "custom"
    assert relation.license_snapshot["rights_chain"][0]["license_text_snapshot"] == source.license_text_snapshot
    assert relation.license_snapshot["custom_license_acknowledgement"]["acknowledged"] is True
    assert relation.license_snapshot["custom_license_acknowledgement"]["acknowledged_by"] == str(derivative_author.id)


@pytest.mark.asyncio
async def test_custom_ancestor_terms_propagate_through_multiple_generations(
    db_session, monkeypatch
):
    owner, source = await _public_source(db_session, "transitive_custom_owner")
    source.license_code = "custom"
    source.license_text_snapshot = "后代必须保留本来源署名。"
    db_session.add(source)
    first_author = User(username="transitive_first", password_hash="test-hash", bio="")
    second_author = User(username="transitive_second", password_hash="test-hash", bio="")
    db_session.add_all([first_author, second_author])
    await db_session.commit()

    async def allow_audit(*args, **kwargs):
        return True, ""

    async def noop(*args, **kwargs):
        return None

    monkeypatch.setattr(ideas_router, "audit_content", allow_audit)
    monkeypatch.setattr(ideas_router.cache, "delete_pattern", noop)
    monkeypatch.setattr(ideas_router.cache, "delete", noop)

    first = await ideas_router.fork_idea(
        IdeaForkRequest(
            parent_id=str(source.id),
            content="第一代衍生",
            confirm_custom_licenses=True,
        ),
        db_session,
        first_author,
    )
    first_idea = await db_session.get(Idea, uuid.UUID(first.id))
    first_idea.publication_status = "published"
    first_idea.visibility = "public"
    first_idea.license_code = "attribution_adaptation"
    first_idea.license_version = "v1"
    first_idea.allow_fork = True
    first_idea.is_forkable = True
    first_idea.legacy_license_review_status = "confirmed"
    await db_session.commit()

    with pytest.raises(HTTPException) as exc:
        await ideas_router.fork_idea(
            IdeaForkRequest(
                parent_id=str(first_idea.id),
                content="未确认上游自定义条款的第二代衍生",
            ),
            db_session,
            second_author,
        )
    assert exc.value.status_code == 422
    assert exc.value.detail["error"]["code"] == "CUSTOM_LICENSE_CONFIRMATION_REQUIRED"

    second = await ideas_router.fork_idea(
        IdeaForkRequest(
            parent_id=str(first_idea.id),
            content="确认全部上游条款后的第二代衍生",
            confirm_custom_licenses=True,
        ),
        db_session,
        second_author,
    )
    second_relation = await db_session.scalar(
        select(ForkRelation).where(
            ForkRelation.child_id == uuid.UUID(second.id)
        )
    )
    chain = second_relation.license_snapshot["rights_chain"]
    assert [item["source_idea_id"] for item in chain] == [
        str(source.id), str(first_idea.id)
    ]
    assert chain[0]["license_code"] == "custom"
    assert chain[0]["license_text_snapshot"] == source.license_text_snapshot
    assert chain[1]["license_code"] == "attribution_adaptation"


@pytest.mark.asyncio
async def test_merge_rights_are_intersection_of_all_parent_chains(db_session):
    owner_a, allowed = await _public_source(db_session, "merge_allowed_owner")
    owner_b, blocked = await _public_source(db_session, "merge_blocked_owner")
    blocked.license_code = "attribution"
    blocked.allow_fork = True
    blocked.is_forkable = True
    await db_session.commit()

    with pytest.raises(HTTPException) as exc:
        await evolve_router.collide_confirm(
            CollideConfirmRequest(
                idea_a_id=str(allowed.id),
                idea_b_id=str(blocked.id),
                content="一个来源不允许改编，因此整个碰撞不能创建",
                ai_assisted=False,
            ),
            db_session,
            owner_a,
        )
    assert exc.value.status_code == 403
    assert exc.value.detail["error"]["code"] == "DERIVATIVE_NOT_ALLOWED"


@pytest.mark.asyncio
async def test_publish_cannot_expand_derivative_rights_beyond_ancestors(
    db_session, monkeypatch
):
    owner, restricted_source = await _public_source(
        db_session, "publish_restricted_ancestor"
    )
    restricted_source.allow_fork = False
    restricted_source.is_forkable = False
    child_author = User(username="publish_restricted_child", password_hash="test-hash", bio="")
    db_session.add(child_author)
    await db_session.flush()
    child = Idea(
        content="历史数据中的衍生创意",
        color_hex="#654321",
        source="fork",
        author_id=child_author.id,
        border_style="gold-thin",
    )
    db_session.add(child)
    await db_session.flush()
    db_session.add(ForkRelation(
        child_id=child.id,
        parent_id=restricted_source.id,
        relation_type="fork",
        license_snapshot={
            "source_idea_id": str(restricted_source.id),
            "source_author_id": str(owner.id),
            "source_author_name": owner.username,
            "license_code": "attribution_adaptation",
            "license_version": "v1",
            "allow_fork": False,
        },
    ))
    await db_session.commit()

    async def allow_audit(*args, **kwargs):
        return True, ""

    async def noop(*args, **kwargs):
        return None

    monkeypatch.setattr(ideas_router, "audit_content", allow_audit)
    monkeypatch.setattr(ideas_router.cache, "delete_pattern", noop)
    monkeypatch.setattr(ideas_router.cache, "delete", noop)
    with pytest.raises(HTTPException) as exc:
        await ideas_router.publish_idea(
            child.id,
            IdeaPublishRequest(
                license_code="attribution_adaptation",
                allow_fork=True,
                confirm_terms=True,
            ),
            db_session,
            child_author,
        )
    assert exc.value.status_code == 422
    assert exc.value.detail["error"]["code"] == "INHERITED_LICENSE_BLOCKS_DERIVATION"


@pytest.mark.asyncio
async def test_collide_requires_custom_ack_for_all_parent_chains(db_session, monkeypatch):
    owner_a, custom_source = await _public_source(
        db_session, "collide_custom_source_owner"
    )
    owner_b, ordinary_source = await _public_source(
        db_session, "collide_ordinary_source_owner"
    )
    custom_source.license_code = "custom"
    custom_source.license_text_snapshot = "保留本来源署名，不得移除授权声明。"
    child_author = User(
        username="collide_custom_child_author", password_hash="test-hash", bio=""
    )
    db_session.add(child_author)
    await db_session.commit()

    async def allow_audit(*args, **kwargs):
        return True, ""

    monkeypatch.setattr(evolve_router, "audit_content", allow_audit)

    request = CollideConfirmRequest(
        idea_a_id=str(custom_source.id),
        idea_b_id=str(ordinary_source.id),
        content="两个来源交集授权下的碰撞创意",
        ai_assisted=False,
    )
    with pytest.raises(HTTPException) as exc:
        await evolve_router.collide_confirm(request, db_session, child_author)
    assert exc.value.status_code == 422
    assert exc.value.detail["error"]["code"] == "CUSTOM_LICENSE_CONFIRMATION_REQUIRED"

    request.confirm_custom_licenses = True
    merged = await evolve_router.collide_confirm(request, db_session, child_author)
    relations = (
        await db_session.execute(
            select(ForkRelation).where(
                ForkRelation.child_id == uuid.UUID(merged.id)
            )
        )
    ).scalars().all()
    assert len(relations) == 2
    custom_relation = next(
        relation for relation in relations
        if relation.license_snapshot["license_code"] == "custom"
    )
    assert custom_relation.license_snapshot[
        "custom_license_acknowledgement"
    ]["acknowledged"] is True


@pytest.mark.asyncio
async def test_evolve_requires_custom_ancestor_ack_before_creation(db_session, monkeypatch):
    owner, source = await _public_source(db_session, "evolve_custom_owner")
    source.license_code = "custom"
    source.license_text_snapshot = "衍生作品必须保留来源署名。"
    child_author = User(
        username="evolve_custom_child_author", password_hash="test-hash", bio=""
    )
    db_session.add(child_author)
    await db_session.commit()

    async def allow_audit(*args, **kwargs):
        return True, ""

    monkeypatch.setattr(evolve_router, "audit_content", allow_audit)

    request = EvolveConfirmRequest(
        parent_id=str(source.id),
        angle="adapt",
        content="明确继承上游授权的演化创意",
        ai_assisted=False,
    )
    with pytest.raises(HTTPException) as exc:
        await evolve_router.evolve_confirm(request, db_session, child_author)
    assert exc.value.status_code == 422
    assert exc.value.detail["error"]["code"] == "CUSTOM_LICENSE_CONFIRMATION_REQUIRED"

    request.confirm_custom_licenses = True
    evolved = await evolve_router.evolve_confirm(request, db_session, child_author)
    relation = await db_session.scalar(
        select(ForkRelation).where(
            ForkRelation.child_id == uuid.UUID(evolved.id)
        )
    )
    assert relation.license_snapshot["license_code"] == "custom"
    assert relation.license_snapshot[
        "custom_license_acknowledgement"
    ]["acknowledged"] is True
    assert relation.license_snapshot[
        "custom_license_acknowledgement"
    ]["acknowledged_by"] == str(child_author.id)
