import uuid
from datetime import datetime, timezone

import pytest
from starlette.requests import Request

from models import User, Idea, IdeaContribution, IdeaVersion, IdeaVersionContribution
from routers.users import get_user_contributions


def _request():
    return Request({
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/api/users/test/contributions",
        "raw_path": b"/api/users/test/contributions",
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
    })


async def _user(db, username):
    user = User(username=username, password_hash="test-hash", bio="")
    db.add(user)
    await db.flush()
    return user


async def _idea(db, owner, visibility):
    idea = Idea(
        content="公开创意内容" if visibility == "public" else "私有创意内容",
        color_hex="#123456",
        source="ugc",
        author_id=owner.id,
        border_style="gold-thin",
        publication_status="published",
        visibility=visibility,
        status="active",
    )
    db.add(idea)
    await db.flush()
    return idea


@pytest.mark.asyncio
async def test_profile_contributions_only_include_published_versions_of_public_ideas(db_session):
    contributor = await _user(db_session, "profile_contributor")
    owner = await _user(db_session, "profile_idea_owner")
    public_idea = await _idea(db_session, owner, "public")
    private_idea = await _idea(db_session, owner, "private")
    now = datetime.now(timezone.utc)

    public_version = IdeaVersion(
        idea_id=public_idea.id,
        version_number=1,
        content_snapshot="公开版本最终内容",
        change_summary="采纳协作者建议",
        status="published",
        created_by=owner.id,
        published_by=owner.id,
        published_at=now,
    )
    private_version = IdeaVersion(
        idea_id=private_idea.id,
        version_number=1,
        content_snapshot="私有版本最终内容",
        change_summary="私有贡献",
        status="published",
        created_by=owner.id,
        published_by=owner.id,
        published_at=now,
    )
    draft_version = IdeaVersion(
        idea_id=public_idea.id,
        version_number=2,
        content_snapshot="尚未公开的草稿",
        status="draft",
        created_by=owner.id,
    )
    db_session.add_all([public_version, private_version, draft_version])
    await db_session.flush()

    public_contribution = IdeaContribution(
        idea_id=public_idea.id, author_id=contributor.id,
        content="提出公开产品场景建议", status="accepted",
    )
    private_contribution = IdeaContribution(
        idea_id=private_idea.id, author_id=contributor.id,
        content="私有项目的内部建议", status="accepted",
    )
    draft_contribution = IdeaContribution(
        idea_id=public_idea.id, author_id=contributor.id,
        content="草稿中的建议", status="accepted",
    )
    db_session.add_all([public_contribution, private_contribution, draft_contribution])
    await db_session.flush()

    public_attribution = IdeaVersionContribution(
        version_id=public_version.id,
        contribution_id=public_contribution.id,
        author_id_snapshot=contributor.id,
        author_name_snapshot="profile_contributor",
        content_snapshot="提出公开产品场景建议",
    )
    private_attribution = IdeaVersionContribution(
        version_id=private_version.id,
        contribution_id=private_contribution.id,
        author_id_snapshot=contributor.id,
        author_name_snapshot="profile_contributor",
        content_snapshot="私有项目的内部建议",
    )
    draft_attribution = IdeaVersionContribution(
        version_id=draft_version.id,
        contribution_id=draft_contribution.id,
        author_id_snapshot=contributor.id,
        author_name_snapshot="profile_contributor",
        content_snapshot="草稿中的建议",
    )
    db_session.add_all([public_attribution, private_attribution, draft_attribution])
    await db_session.commit()

    result = await get_user_contributions(
        _request(), contributor.id, 20, 0, db_session
    )

    assert result["total"] == 1
    assert len(result["items"]) == 1
    item = result["items"][0]
    assert item["idea_id"] == str(public_idea.id)
    assert item["version_number"] == 1
    assert item["idea_content"] == "公开版本最终内容"
    assert item["contribution_content"] == "提出公开产品场景建议"
    assert item["author_name"] == "profile_contributor"
    assert result["has_more"] is False
