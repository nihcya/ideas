"""HTTP-level regression tests for the public contribution discovery flow."""
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from deps import get_db
from main import app
from models import User, Idea, IdeaContribution, IdeaVersion, IdeaVersionContribution


async def _user(db, username):
    user = User(username=username, password_hash="test-hash", bio="")
    db.add(user)
    await db.flush()
    return user


async def _idea(db, owner, *, visibility="public", status="active"):
    idea = Idea(
        content="公开创意内容",
        color_hex="#123456",
        source="ugc",
        author_id=owner.id,
        border_style="gold-thin",
        publication_status="published",
        visibility=visibility,
        status=status,
        published_at=datetime.now(timezone.utc),
    )
    db.add(idea)
    await db.flush()
    return idea


@pytest.mark.asyncio
async def test_public_timeline_http_contract_enforces_public_era_and_frozen_attribution(db_session):
    owner = await _user(db_session, "http_timeline_owner")
    contributor = await _user(db_session, "http_timeline_contributor")
    idea = await _idea(db_session, owner)
    private_idea = await _idea(db_session, owner, visibility="private")
    inactive_idea = await _idea(db_session, owner, status="faded")
    public_since = idea.published_at

    private_era = IdeaVersion(
        idea_id=idea.id,
        version_number=1,
        content_snapshot="公开前的私有快照",
        status="published",
        created_by=owner.id,
        published_by=owner.id,
        published_at=public_since - timedelta(days=1),
    )
    public_era = IdeaVersion(
        idea_id=idea.id,
        version_number=2,
        content_snapshot="公开后的版本快照",
        change_summary="纳入协作者建议",
        status="published",
        created_by=owner.id,
        published_by=owner.id,
        published_at=public_since + timedelta(minutes=1),
    )
    draft = IdeaVersion(
        idea_id=idea.id,
        version_number=3,
        content_snapshot="未发布草稿",
        status="draft",
        created_by=owner.id,
    )
    private_version = IdeaVersion(
        idea_id=private_idea.id,
        version_number=1,
        content_snapshot="私有创意版本",
        status="published",
        created_by=owner.id,
        published_by=owner.id,
        published_at=public_since + timedelta(minutes=2),
    )
    inactive_version = IdeaVersion(
        idea_id=inactive_idea.id,
        version_number=1,
        content_snapshot="已撤回创意版本",
        status="published",
        created_by=owner.id,
        published_by=owner.id,
        published_at=public_since + timedelta(minutes=2),
    )
    db_session.add_all([private_era, public_era, draft, private_version, inactive_version])
    await db_session.flush()

    contribution = IdeaContribution(
        idea_id=idea.id,
        author_id=contributor.id,
        content="可变的当前贡献正文",
        status="accepted",
    )
    db_session.add(contribution)
    await db_session.flush()
    db_session.add(IdeaVersionContribution(
        version_id=public_era.id,
        contribution_id=contribution.id,
        author_id_snapshot=contributor.id,
        author_name_snapshot="发布时冻结的用户名",
        content_snapshot="发布时冻结的贡献内容",
    ))
    await db_session.commit()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.get(f"/api/ideas/{idea.id}/versions/public")
            private_response = await client.get(
                f"/api/ideas/{private_idea.id}/versions/public"
            )
            inactive_response = await client.get(
                f"/api/ideas/{inactive_idea.id}/versions/public"
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    payload = response.json()
    assert [item["version_number"] for item in payload["items"]] == [2]
    attribution = payload["items"][0]["attributions"][0]
    assert attribution["author_name"] == "发布时冻结的用户名"
    assert attribution["content"] == "发布时冻结的贡献内容"
    assert private_response.status_code == 404
    assert inactive_response.status_code == 404


@pytest.mark.asyncio
async def test_public_contribution_feed_http_contract_paginates_and_hides_private_data(db_session):
    contributor = await _user(db_session, "http_feed_contributor")
    owner = await _user(db_session, "http_feed_owner")
    idea = await _idea(db_session, owner)
    private_idea = await _idea(db_session, owner, visibility="private")
    now = datetime.now(timezone.utc)

    versions = [
        IdeaVersion(
            idea_id=idea.id,
            version_number=index,
            content_snapshot=f"公开版本 {index}",
            status="published",
            created_by=owner.id,
            published_by=owner.id,
            published_at=now + timedelta(minutes=index),
        )
        for index in (1, 2)
    ]
    private_version = IdeaVersion(
        idea_id=private_idea.id,
        version_number=1,
        content_snapshot="私有版本",
        status="published",
        created_by=owner.id,
        published_by=owner.id,
        published_at=now + timedelta(minutes=3),
    )
    db_session.add_all([*versions, private_version])
    await db_session.flush()

    contributions = [
        IdeaContribution(
            idea_id=idea.id,
            author_id=contributor.id,
            content=f"公开贡献 {index}",
            status="accepted",
        )
        for index in (1, 2)
    ]
    private_contribution = IdeaContribution(
        idea_id=private_idea.id,
        author_id=contributor.id,
        content="私有贡献",
        status="accepted",
    )
    db_session.add_all([*contributions, private_contribution])
    await db_session.flush()

    for version, contribution in zip(versions, contributions):
        db_session.add(IdeaVersionContribution(
            version_id=version.id,
            contribution_id=contribution.id,
            author_id_snapshot=contributor.id,
            author_name_snapshot="冻结署名",
            content_snapshot=f"冻结贡献 {version.version_number}",
        ))
    db_session.add(IdeaVersionContribution(
        version_id=private_version.id,
        contribution_id=private_contribution.id,
        author_id_snapshot=contributor.id,
        author_name_snapshot="私有署名",
        content_snapshot="私有冻结内容",
    ))
    await db_session.commit()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.get(
                f"/api/users/{contributor.id}/contributions",
                params={"limit": 1, "offset": 1},
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert payload["limit"] == 1
    assert payload["offset"] == 1
    assert payload["has_more"] is False
    assert len(payload["items"]) == 1
    assert payload["items"][0]["author_name"] == "冻结署名"
    assert payload["items"][0]["contribution_content"] == "冻结贡献 1"
