import uuid

import pytest

from models import User, Idea
from routers import ideas as ideas_router
from schemas.idea import IdeaInviteRequest
from services.idea_access import can_view_idea


async def _user(db, username):
    user = User(username=username, password_hash="test-hash", bio="")
    db.add(user)
    await db.flush()
    return user


async def _private_idea(db, owner_id):
    idea = Idea(
        content="受邀访问的私有创意",
        color_hex="#123456",
        source="ugc",
        author_id=owner_id,
        border_style="gold-thin",
    )
    db.add(idea)
    await db.flush()
    return idea


@pytest.mark.asyncio
async def test_private_invite_lifecycle_and_revocation(monkeypatch, db_session):
    async def noop_delete(*args, **kwargs):
        return None

    monkeypatch.setattr(ideas_router.cache, "delete", noop_delete)

    owner = await _user(db_session, "invite_lifecycle_owner")
    invitee = await _user(db_session, "invite_lifecycle_invitee")
    idea = await _private_idea(db_session, owner.id)

    created = await ideas_router.invite_to_private_idea(
        idea.id,
        IdeaInviteRequest(user_id=str(invitee.id), role="contributor"),
        db_session,
        owner,
    )
    invite_id = uuid.UUID(created["invite_id"])
    assert created["status"] == "pending"
    assert await can_view_idea(db_session, idea, invitee.id) is False

    inbox = await ideas_router.list_pending_idea_invites(db_session, invitee)
    assert len(inbox["items"]) == 1
    assert inbox["items"][0]["invite_id"] == str(invite_id)

    accepted = await ideas_router.accept_private_idea_invite(
        idea.id, invite_id, db_session, invitee
    )
    assert accepted["accepted"] is True
    assert await can_view_idea(db_session, idea, invitee.id) is True

    owner_list = await ideas_router.list_idea_invites(idea.id, db_session, owner)
    assert owner_list["items"][0]["status"] == "accepted"

    revoked = await ideas_router.revoke_private_idea_invite(
        idea.id, invite_id, db_session, owner
    )
    assert revoked["revoked"] is True
    assert await can_view_idea(db_session, idea, invitee.id) is False


@pytest.mark.asyncio
async def test_private_invite_can_be_declined(monkeypatch, db_session):
    async def noop_delete(*args, **kwargs):
        return None

    monkeypatch.setattr(ideas_router.cache, "delete", noop_delete)
    owner = await _user(db_session, "invite_decline_owner")
    invitee = await _user(db_session, "invite_decline_invitee")
    idea = await _private_idea(db_session, owner.id)

    created = await ideas_router.invite_to_private_idea(
        idea.id,
        IdeaInviteRequest(user_id=str(invitee.id), role="viewer"),
        db_session,
        owner,
    )
    invite_id = uuid.UUID(created["invite_id"])

    declined = await ideas_router.decline_private_idea_invite(
        idea.id, invite_id, db_session, invitee
    )
    assert declined["declined"] is True
    assert await can_view_idea(db_session, idea, invitee.id) is False



@pytest.mark.asyncio
async def test_pending_invite_cannot_be_accepted_after_idea_becomes_public(monkeypatch, db_session):
    from fastapi import HTTPException
    from models import IdeaAccessGrant

    async def noop_delete(*args, **kwargs):
        return None

    monkeypatch.setattr(ideas_router.cache, "delete", noop_delete)
    owner = await _user(db_session, "invite_stale_owner")
    invitee = await _user(db_session, "invite_stale_invitee")
    idea = await _private_idea(db_session, owner.id)
    created = await ideas_router.invite_to_private_idea(
        idea.id,
        IdeaInviteRequest(user_id=str(invitee.id), role="viewer"),
        db_session,
        owner,
    )
    invite_id = uuid.UUID(created["invite_id"])

    idea.visibility = "public"
    await db_session.flush()
    with pytest.raises(HTTPException) as exc:
        await ideas_router.accept_private_idea_invite(
            idea.id, invite_id, db_session, invitee
        )
    assert exc.value.status_code == 409

    grant = await db_session.get(IdeaAccessGrant, invite_id)
    assert grant.status == "pending"
    assert await can_view_idea(db_session, idea, invitee.id) is True
