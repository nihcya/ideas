import pytest

from models import User, Idea, ForkRelation
from services.idea_access import build_derivation_snapshot, can_derive_from_idea


async def _user(db, username):
    user = User(username=username, password_hash="test-hash", bio="")
    db.add(user)
    await db.flush()
    return user


async def _public_source(db, owner, content, *, allow_fork=True):
    idea = Idea(
        content=content,
        color_hex="#123456",
        source="ugc",
        author_id=owner.id,
        border_style="gold-thin",
        status="active",
        publication_status="published",
        visibility="public",
        license_code="attribution_adaptation",
        license_version="v1",
        allow_fork=allow_fork,
        is_forkable=allow_fork,
        legacy_license_review_status="not_required",
    )
    db.add(idea)
    await db.flush()
    return idea


async def _child(db, owner, content):
    idea = Idea(
        content=content,
        color_hex="#654321",
        source="merge",
        author_id=owner.id,
        border_style="gold-thin",
        status="active",
        publication_status="published",
        visibility="public",
        license_code="attribution_adaptation",
        license_version="v1",
        allow_fork=True,
        is_forkable=True,
        legacy_license_review_status="not_required",
    )
    db.add(idea)
    await db.flush()
    return idea


@pytest.mark.asyncio
async def test_multi_parent_derivation_requires_intersection_of_every_parent_license(db_session):
    owner = await _user(db_session, "lineage_multi_owner")
    parent_a = await _public_source(db_session, owner, "允许衍生的上游 A")
    parent_b = await _public_source(db_session, owner, "允许衍生的上游 B")
    allowed_child = await _child(db_session, owner, "双父授权均允许的合并创意")
    snapshot_a = await build_derivation_snapshot(db_session, parent_a)
    snapshot_b = await build_derivation_snapshot(db_session, parent_b)
    db_session.add_all([
        ForkRelation(
            child_id=allowed_child.id,
            parent_id=parent_a.id,
            relation_type="merge",
            license_snapshot=snapshot_a,
        ),
        ForkRelation(
            child_id=allowed_child.id,
            parent_id=parent_b.id,
            relation_type="merge",
            license_snapshot=snapshot_b,
        ),
    ])

    parent_c = await _public_source(db_session, owner, "禁止继续衍生的上游 C", allow_fork=False)
    denied_child = await _child(db_session, owner, "其中一个父来源禁止衍生")
    snapshot_c = await build_derivation_snapshot(db_session, parent_c)
    db_session.add(ForkRelation(
        child_id=denied_child.id,
        parent_id=parent_a.id,
        relation_type="merge",
        license_snapshot=snapshot_a,
    ))
    db_session.add(ForkRelation(
        child_id=denied_child.id,
        parent_id=parent_c.id,
        relation_type="merge",
        license_snapshot=snapshot_c,
    ))
    await db_session.commit()

    assert await can_derive_from_idea(db_session, allowed_child, owner.id) is True
    assert await can_derive_from_idea(db_session, denied_child, owner.id) is False


@pytest.mark.asyncio
async def test_existing_derivative_keeps_frozen_rights_after_original_is_withdrawn(db_session):
    owner = await _user(db_session, "lineage_withdraw_owner")
    parent = await _public_source(db_session, owner, "原始公开创意")
    child = await _child(db_session, owner, "已经创建的衍生创意")
    snapshot = await build_derivation_snapshot(db_session, parent)
    db_session.add(ForkRelation(
        child_id=child.id,
        parent_id=parent.id,
        relation_type="fork",
        license_snapshot=snapshot,
    ))
    await db_session.commit()

    # Original creator withdraws the source after the derivative already exists.
    parent.publication_status = "draft"
    parent.visibility = "private"
    parent.allow_fork = False
    parent.is_forkable = False
    await db_session.commit()

    assert await can_derive_from_idea(db_session, parent, owner.id) is False
    assert await can_derive_from_idea(db_session, child, owner.id) is True
