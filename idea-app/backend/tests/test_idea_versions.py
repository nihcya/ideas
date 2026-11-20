import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from models import User, Idea, IdeaContribution, IdeaVersion, IdeaVersionContribution
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


@pytest.mark.asyncio
async def test_diff_compares_only_published_versions_of_owned_idea(db_session):
    owner = await _user(db_session, "version_diff_owner")
    other = await _user(db_session, "version_diff_other")
    idea = await _idea(db_session, owner)
    now = datetime.now(timezone.utc)
    old = IdeaVersion(
        idea_id=idea.id, version_number=1, content_snapshot="创意原始内容",
        change_summary="初始版本", status="published", created_by=owner.id,
        published_by=owner.id, published_at=now,
    )
    new = IdeaVersion(
        idea_id=idea.id, version_number=2, content_snapshot="创意新增校园场景",
        change_summary="增加校园场景", status="published", created_by=owner.id,
        published_by=owner.id, published_at=now,
    )
    draft = IdeaVersion(
        idea_id=idea.id, version_number=3, content_snapshot="未发布草稿",
        status="draft", created_by=owner.id,
    )
    db_session.add_all([old, new, draft])
    await db_session.commit()

    result = await versions_router.compare_published_versions(
        idea.id, new.id, old.id, db_session, owner
    )
    assert result["from_version"]["version_number"] == 1
    assert result["to_version"]["version_number"] == 2
    assert any(segment["type"] in ("replace", "insert") and "校园场景" in segment["new_text"]
               for segment in result["segments"])

    with pytest.raises(HTTPException) as draft_error:
        await versions_router.compare_published_versions(
            idea.id, draft.id, old.id, db_session, owner
        )
    assert draft_error.value.status_code == 404

    with pytest.raises(HTTPException) as acl_error:
        await versions_router.compare_published_versions(
            idea.id, new.id, old.id, db_session, other
        )
    assert acl_error.value.status_code == 404


@pytest.mark.asyncio
async def test_public_timeline_exposes_only_public_era_published_versions(db_session):
    owner = await _user(db_session, "public_timeline_owner")
    now = datetime.now(timezone.utc)
    public_idea = Idea(
        content="公开创意当前内容", color_hex="#123456", source="ugc",
        author_id=owner.id, border_style="gold-thin",
        publication_status="published", visibility="public", status="active",
        published_at=now,
    )
    private_idea = Idea(
        content="私有创意内容", color_hex="#123456", source="ugc",
        author_id=owner.id, border_style="gold-thin",
        publication_status="published", visibility="private", status="active",
        published_at=now,
    )
    db_session.add_all([public_idea, private_idea])
    await db_session.flush()
    private_era_version = IdeaVersion(
        idea_id=public_idea.id, version_number=1,
        content_snapshot="转公开前的私有版本", change_summary="私有阶段版本",
        status="published", created_by=owner.id,
        published_by=owner.id, published_at=now - timedelta(days=1),
    )
    public_era_version = IdeaVersion(
        idea_id=public_idea.id, version_number=2,
        content_snapshot="公开之后发布的版本", change_summary="公开阶段更新",
        status="published", created_by=owner.id,
        published_by=owner.id, published_at=now + timedelta(days=1),
    )
    public_draft = IdeaVersion(
        idea_id=public_idea.id, version_number=3,
        content_snapshot="不应公开的草稿", status="draft", created_by=owner.id,
    )
    inactive_idea = Idea(
        content="已撤回的公开创意", color_hex="#123456", source="ugc",
        author_id=owner.id, border_style="gold-thin",
        publication_status="published", visibility="public", status="faded",
        published_at=now,
    )
    private_version = IdeaVersion(
        idea_id=private_idea.id, version_number=1,
        content_snapshot="私有版本快照", status="published",
        created_by=owner.id, published_by=owner.id, published_at=now + timedelta(days=1),
    )
    inactive_version = IdeaVersion(
        idea_id=inactive_idea.id, version_number=1,
        content_snapshot="不可再公开读取的历史版本", status="published",
        created_by=owner.id, published_by=owner.id,
        published_at=now + timedelta(days=1),
    )
    db_session.add_all([
        private_era_version, public_era_version, public_draft, private_version,
        inactive_version,
    ])
    await db_session.flush()
    contributor = await _user(db_session, "public_timeline_contributor")
    contribution = IdeaContribution(
        idea_id=public_idea.id, author_id=contributor.id,
        content="原始协作建议", status="accepted",
    )
    db_session.add(contribution)
    await db_session.flush()
    db_session.add(IdeaVersionContribution(
        version_id=public_era_version.id,
        contribution_id=contribution.id,
        author_id_snapshot=contributor.id,
        author_name_snapshot="发布时的署名",
        content_snapshot="发布时冻结的建议文本",
    ))
    await db_session.commit()

    result = await versions_router.list_public_versions(public_idea.id, db_session)
    assert len(result["items"]) == 1
    assert result["items"][0]["version_number"] == 2
    assert result["items"][0]["content"] == "公开之后发布的版本"
    assert result["items"][0]["attributions"][0]["author_name"] == "发布时的署名"
    assert result["items"][0]["attributions"][0]["content"] == "发布时冻结的建议文本"

    with pytest.raises(HTTPException) as inactive_error:
        await versions_router.list_public_versions(inactive_idea.id, db_session)
    assert inactive_error.value.status_code == 404

    with pytest.raises(HTTPException) as private_error:
        await versions_router.list_public_versions(private_idea.id, db_session)
    assert private_error.value.status_code == 404



@pytest.mark.asyncio
async def test_public_idea_owner_can_create_and_publish_versions_without_changing_rights(db_session):
    owner = await _user(db_session, "public_version_owner")
    idea = Idea(
        content="公开创意初始内容", color_hex="#123456", source="ugc",
        author_id=owner.id, border_style="gold-thin",
        publication_status="published", visibility="public", status="active",
        published_at=datetime.now(timezone.utc),
        license_code="CC-BY-4.0", allow_fork=True,
    )
    db_session.add(idea)
    await db_session.commit()
    original_published_at = idea.published_at

    draft = await versions_router.create_version_draft(
        idea.id,
        VersionDraftCreate(content="公开创意的后续版本", change_summary="公开后持续迭代"),
        db_session,
        owner,
    )
    assert draft["status"] == "draft"

    await versions_router.update_version_draft(
        idea.id,
        uuid.UUID(draft["id"]),
        VersionDraftUpdate(
            content="公开创意迭代后的最终版本",
            change_summary="作者更新公开阶段草稿",
        ),
        db_session,
        owner,
    )
    published = await versions_router.publish_version(
        idea.id, uuid.UUID(draft["id"]), db_session, owner
    )
    assert published["published"] is True
    assert idea.content == "公开创意迭代后的最终版本"
    assert idea.visibility == "public"
    assert idea.publication_status == "published"
    assert idea.status == "active"
    assert idea.license_code == "CC-BY-4.0"
    assert idea.allow_fork is True
    assert idea.published_at == original_published_at


@pytest.mark.asyncio
async def test_non_owner_cannot_manage_public_idea_versions(db_session):
    owner = await _user(db_session, "public_version_acl_owner")
    other = await _user(db_session, "public_version_acl_other")
    idea = Idea(
        content="作者的公开创意", color_hex="#123456", source="ugc",
        author_id=owner.id, border_style="gold-thin",
        publication_status="published", visibility="public", status="active",
        published_at=datetime.now(timezone.utc),
    )
    db_session.add(idea)
    await db_session.commit()

    with pytest.raises(HTTPException) as exc:
        await versions_router.create_version_draft(
            idea.id, VersionDraftCreate(content="越权修改"),
            db_session, other,
        )
    assert exc.value.status_code == 404
