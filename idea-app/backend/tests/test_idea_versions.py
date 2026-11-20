import uuid

import pytest
from fastapi import HTTPException

from models import User, Idea, IdeaContribution
from routers import idea_versions as versions_router
from routers.idea_versions import VersionDraftCreate, VersionDraftUpdate


@pytest.fixture(autouse=True)
def allow_version_audit(monkeypatch):
    async def allow(*args, **kwargs):
        return True, ""
    async def noop(*args, **kwargs):
        return None
    monkeypatch.setattr(versions_router, "audit_content", allow)
    monkeypatch.setattr(versions_router, "write_audit_log", noop)


async def _user(db, username):
    user = User(username=username, password_hash="test-hash", bio="")
    db.add(user)
    await db.flush()
    return user


async def _idea(db, owner):
    idea = Idea(
        content="版本管理原始内容", color_hex="#123456", source="ugc",
        author_id=owner.id, border_style="gold-thin",
        publication_status="draft", visibility="private",
    )
    db.add(idea)
    await db.flush()
    return idea


@pytest.mark.asyncio
async def test_author_creates_and_publishes_version_with_frozen_attribution(db_session):
    owner = await _user(db_session, "version_owner")
    contributor = await _user(db_session, "version_contributor")
    idea = await _idea(db_session, owner)
    contribution = IdeaContribution(
        idea_id=idea.id, author_id=contributor.id,
        content="增加面向学校的应用场景", status="accepted",
    )
    db_session.add(contribution)
    await db_session.commit()

    draft = await versions_router.create_version_draft(
        idea.id,
        VersionDraftCreate(
            content="加入校园应用场景后的新创意",
            change_summary="采纳校园场景建议",
            contribution_ids=[contribution.id],
        ),
        db_session,
        owner,
    )
    version_id = uuid.UUID(draft["id"])
    assert draft["status"] == "draft"
    assert idea.content == "版本管理原始内容"

    published = await versions_router.publish_version(
        idea.id, version_id, db_session, owner
    )
    assert published["published"] is True
    assert idea.content == "加入校园应用场景后的新创意"
    assert published["version"]["attributions"][0]["author_name"] == "version_contributor"


@pytest.mark.asyncio
async def test_non_owner_cannot_create_or_publish_version(db_session):
    owner = await _user(db_session, "version_acl_owner")
    other = await _user(db_session, "version_acl_other")
    idea = await _idea(db_session, owner)

    with pytest.raises(HTTPException) as exc:
        await versions_router.create_version_draft(
            idea.id, VersionDraftCreate(content="越权版本"), db_session, other
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_unaccepted_contribution_cannot_be_added_to_version(db_session):
    owner = await _user(db_session, "version_pending_owner")
    contributor = await _user(db_session, "version_pending_author")
    idea = await _idea(db_session, owner)
    contribution = IdeaContribution(
        idea_id=idea.id, author_id=contributor.id,
        content="尚未审核", status="submitted",
    )
    db_session.add(contribution)
    await db_session.commit()

    with pytest.raises(HTTPException) as exc:
        await versions_router.create_version_draft(
            idea.id,
            VersionDraftCreate(content="整合后的版本", contribution_ids=[contribution.id]),
            db_session,
            owner,
        )
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_published_version_is_locked_and_contribution_cannot_be_reused(db_session):
    owner = await _user(db_session, "version_lock_owner")
    contributor = await _user(db_session, "version_lock_author")
    idea = await _idea(db_session, owner)
    contribution = IdeaContribution(
        idea_id=idea.id, author_id=contributor.id,
        content="唯一归属的贡献", status="accepted",
    )
    db_session.add(contribution)
    await db_session.commit()
    draft = await versions_router.create_version_draft(
        idea.id,
        VersionDraftCreate(content="第一版", contribution_ids=[contribution.id]),
        db_session,
        owner,
    )
    version_id = uuid.UUID(draft["id"])
    await versions_router.publish_version(idea.id, version_id, db_session, owner)

    with pytest.raises(HTTPException) as exc:
        await versions_router.update_version_draft(
            idea.id, version_id,
            VersionDraftUpdate(content="篡改已发布版本"),
            db_session, owner,
        )
    assert exc.value.status_code == 404

    with pytest.raises(HTTPException) as reused:
        await versions_router.create_version_draft(
            idea.id,
            VersionDraftCreate(content="第二版", contribution_ids=[contribution.id]),
            db_session, owner,
        )
    assert reused.value.status_code == 409


@pytest.mark.asyncio
async def test_contribution_list_links_to_published_version_and_preserves_snapshot(db_session):
    owner = await _user(db_session, "version_trace_owner")
    contributor = await _user(db_session, "version_trace_author")
    idea = await _idea(db_session, owner)
    contribution = IdeaContribution(
        idea_id=idea.id,
        author_id=contributor.id,
        content="原始贡献文本",
        status="accepted",
    )
    db_session.add(contribution)
    await db_session.commit()

    draft = await versions_router.create_version_draft(
        idea.id,
        VersionDraftCreate(
            content="发布后的创意版本",
            change_summary="采纳协作者建议",
            contribution_ids=[contribution.id],
        ),
        db_session,
        owner,
    )
    await versions_router.publish_version(
        idea.id, uuid.UUID(draft["id"]), db_session, owner
    )

    from routers.ideas import list_idea_contributions

    result = await list_idea_contributions(idea.id, db_session, owner)
    linked = next(item for item in result["items"] if item["id"] == str(contribution.id))
    assert linked["published_version"]["version_number"] == 1
    assert linked["published_version"]["change_summary"] == "采纳协作者建议"
    assert linked["attribution_content_snapshot"] == "原始贡献文本"
    assert linked["attribution_author_name"] == "version_trace_author"
