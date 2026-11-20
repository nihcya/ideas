import uuid

import pytest
from fastapi import HTTPException

from models import User, Idea
from routers import ideas as ideas_router
from schemas.idea import (
    IdeaInviteRequest,
    IdeaContributionCreate,
    IdeaContributionReview,
)
from services.idea_access import can_view_idea


@pytest.fixture(autouse=True)
def disable_cache_calls(monkeypatch):
    async def noop_delete(*args, **kwargs):
        return None
    monkeypatch.setattr(ideas_router.cache, "delete", noop_delete)


async def _user(db, username):
    user = User(username=username, password_hash="test-hash", bio="")
    db.add(user)
    await db.flush()
    return user


async def _private_idea(db, owner_id):
    idea = Idea(
        content="协作贡献测试创意",
        color_hex="#123456",
        source="ugc",
        author_id=owner_id,
        border_style="gold-thin",
        publication_status="draft",
        visibility="private",
    )
    db.add(idea)
    await db.flush()
    return idea


async def _invite_and_accept(db, idea, owner, contributor, role="contributor"):
    created = await ideas_router.invite_to_private_idea(
        idea.id,
        IdeaInviteRequest(user_id=str(contributor.id), role=role),
        db,
        owner,
    )
    return await ideas_router.accept_private_idea_invite(
        idea.id, uuid.UUID(created["invite_id"]), db, contributor
    )


@pytest.mark.asyncio
async def test_contributor_submit_owner_reviews_and_contribution_is_separate(db_session):
    owner = await _user(db_session, "contribution_owner")
    contributor = await _user(db_session, "contribution_author")
    idea = await _private_idea(db_session, owner.id)
    await _invite_and_accept(db_session, idea, owner, contributor)

    created = await ideas_router.submit_idea_contribution(
        idea.id,
        IdeaContributionCreate(content="增加面向校园场景的落地方案", note="补充使用场景"),
        db_session,
        contributor,
    )
    contribution_id = uuid.UUID(created["id"])
    assert created["status"] == "submitted"
    assert idea.content == "协作贡献测试创意"

    contributor_list = await ideas_router.list_idea_contributions(
        idea.id, db_session, contributor
    )
    owner_list = await ideas_router.list_idea_contributions(
        idea.id, db_session, owner
    )
    assert len(contributor_list["items"]) == 1
    assert len(owner_list["items"]) == 1

    reviewed = await ideas_router.review_idea_contribution(
        idea.id,
        contribution_id,
        IdeaContributionReview(decision="accepted", review_note="建议采纳"),
        db_session,
        owner,
    )
    assert reviewed["status"] == "accepted"
    assert idea.content == "协作贡献测试创意"


@pytest.mark.asyncio
async def test_viewer_cannot_submit_and_contributor_cannot_review(db_session):
    owner = await _user(db_session, "contribution_acl_owner")
    viewer = await _user(db_session, "contribution_acl_viewer")
    idea = await _private_idea(db_session, owner.id)
    await _invite_and_accept(db_session, idea, owner, viewer, role="viewer")

    with pytest.raises(HTTPException) as exc:
        await ideas_router.submit_idea_contribution(
            idea.id,
            IdeaContributionCreate(content="越权提交"),
            db_session,
            viewer,
        )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_contributor_cannot_review_own_or_other_contributions(db_session):
    owner = await _user(db_session, "contribution_review_owner")
    contributor = await _user(db_session, "contribution_review_author")
    idea = await _private_idea(db_session, owner.id)
    await _invite_and_accept(db_session, idea, owner, contributor)
    created = await ideas_router.submit_idea_contribution(
        idea.id, IdeaContributionCreate(content="提交建议"), db_session, contributor
    )

    with pytest.raises(HTTPException) as exc:
        await ideas_router.review_idea_contribution(
            idea.id,
            uuid.UUID(created["id"]),
            IdeaContributionReview(decision="accepted"),
            db_session,
            contributor,
        )
    assert exc.value.status_code == 404
