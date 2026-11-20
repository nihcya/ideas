import uuid

import pytest

from models import User, Idea, IdeaAccessGrant
from services.idea_access import can_view_idea, can_derive_from_idea, is_public_idea


async def _user(db, username: str) -> User:
    user = User(username=username, password_hash="test-hash", bio="")
    db.add(user)
    await db.flush()
    return user


async def _idea(db, author_id, **overrides) -> Idea:
    values = dict(
        content="测试创意",
        color_hex="#FF6B6B",
        source="ugc",
        author_id=author_id,
        border_style="none",
    )
    values.update(overrides)
    idea = Idea(**values)
    db.add(idea)
    await db.flush()
    return idea


@pytest.mark.asyncio
async def test_private_idea_is_visible_only_to_owner_or_accepted_invitee(db_session):
    owner = await _user(db_session, "acl_owner")
    invitee = await _user(db_session, "acl_invitee")
    stranger = await _user(db_session, "acl_stranger")
    idea = await _idea(db_session, owner.id)

    assert not is_public_idea(idea)
    assert await can_view_idea(db_session, idea, None) is False
    assert await can_view_idea(db_session, idea, stranger.id) is False
    assert await can_view_idea(db_session, idea, owner.id) is True

    grant = IdeaAccessGrant(
        idea_id=idea.id,
        user_id=invitee.id,
        role="viewer",
        status="pending",
        invited_by=owner.id,
    )
    db_session.add(grant)
    await db_session.flush()
    assert await can_view_idea(db_session, idea, invitee.id) is False

    grant.status = "accepted"
    await db_session.flush()
    assert await can_view_idea(db_session, idea, invitee.id) is True

    grant.status = "revoked"
    await db_session.flush()
    assert await can_view_idea(db_session, idea, invitee.id) is False


@pytest.mark.asyncio
async def test_legacy_public_idea_remains_readable_but_not_derivable_while_pending(db_session):
    owner = await _user(db_session, "legacy_owner")
    viewer = await _user(db_session, "legacy_viewer")
    idea = await _idea(
        db_session,
        owner.id,
        publication_status="published",
        visibility="public",
        legacy_license_review_status="pending",
        license_code="legacy_unspecified",
        allow_fork=False,
    )

    assert is_public_idea(idea)
    assert await can_view_idea(db_session, idea, viewer.id) is True
    assert await can_derive_from_idea(db_session, idea, viewer.id) is False

    idea.legacy_license_review_status = "confirmed"
    idea.license_code = "attribution_adaptation"
    idea.allow_fork = True
    await db_session.flush()
    assert await can_derive_from_idea(db_session, idea, viewer.id) is True


@pytest.mark.asyncio
async def test_private_draft_cannot_be_used_as_derivative_source_even_by_owner(db_session):
    owner = await _user(db_session, "private_derivative_owner")
    idea = await _idea(
        db_session,
        owner.id,
        publication_status="draft",
        visibility="private",
        license_code="attribution_adaptation",
        allow_fork=True,
    )
    assert await can_view_idea(db_session, idea, owner.id) is True
    assert await can_derive_from_idea(db_session, idea, owner.id) is False


@pytest.mark.asyncio
async def test_accepted_invitee_can_view_but_not_derive_private_idea(db_session):
    owner = await _user(db_session, "private_source_owner")
    invitee = await _user(db_session, "private_source_invitee")
    idea = await _idea(
        db_session,
        owner.id,
        publication_status="published",
        visibility="private",
        license_code="attribution_adaptation",
        allow_fork=True,
    )
    db_session.add(IdeaAccessGrant(
        idea_id=idea.id,
        user_id=invitee.id,
        role="contributor",
        status="accepted",
        invited_by=owner.id,
    ))
    await db_session.flush()
    assert await can_view_idea(db_session, idea, invitee.id) is True
    assert await can_derive_from_idea(db_session, idea, invitee.id) is False
