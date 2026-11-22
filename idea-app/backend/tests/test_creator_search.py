import pytest
from httpx import ASGITransport, AsyncClient

from deps import get_db
from main import app
from models import (
    User, Idea, IdeaVersion, IdeaContribution, IdeaVersionContribution,
)


async def _user(db, username, bio=""):
    user = User(username=username, password_hash="test-hash", bio=bio)
    db.add(user)
    await db.flush()
    return user


async def _idea(db, owner, content, visibility="public"):
    idea = Idea(
        content=content,
        color_hex="#123456",
        source="ugc",
        author_id=owner.id,
        border_style="gold-thin",
        status="active",
        publication_status="published" if visibility == "public" else "draft",
        visibility=visibility,
        license_code="attribution",
        license_version="v1",
        allow_fork=False,
        legacy_license_review_status="not_required",
    )
    db.add(idea)
    await db.flush()
    return idea


@pytest.mark.asyncio
async def test_public_creator_search_ranks_public_attributions_and_hides_private_only_profiles(db_session):
    creator_a = await _user(db_session, "creator_alpha", "two public ideas")
    creator_b = await _user(db_session, "creator_beta", "public contribution")
    private_only = await _user(db_session, "creator_private_only", "private account")

    await _idea(db_session, creator_a, "alpha public idea one")
    await _idea(db_session, creator_a, "alpha public idea two")
    public_idea_b = await _idea(db_session, creator_b, "beta public idea")
    await _idea(db_session, private_only, "private only idea", visibility="private")

    version = IdeaVersion(
        idea_id=public_idea_b.id,
        version_number=1,
        content_snapshot="published version with attribution",
        status="published",
        created_by=creator_b.id,
        published_by=creator_b.id,
    )
    db_session.add(version)
    await db_session.flush()
    contribution = IdeaContribution(
        idea_id=public_idea_b.id,
        author_id=creator_a.id,
        content="publicly credited collaboration contribution",
        status="accepted",
    )
    db_session.add(contribution)
    await db_session.flush()
    db_session.add(IdeaVersionContribution(
        version_id=version.id,
        contribution_id=contribution.id,
        author_id_snapshot=creator_a.id,
        author_name_snapshot=creator_a.username,
        content_snapshot=contribution.content,
    ))
    await db_session.commit()

    async def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
            response = await client.get("/api/users/search", params={"q": "creator_"})
            assert response.status_code == 200
            items = response.json()["items"]
            ids = [item["id"] for item in items]
            assert str(private_only.id) not in ids
            assert ids[0] == str(creator_a.id)
            alpha = items[0]
            assert alpha["public_idea_count"] == 2
            assert alpha["public_contribution_count"] == 1

            beta = next(item for item in items if item["id"] == str(creator_b.id))
            assert beta["public_idea_count"] == 1
            assert beta["public_contribution_count"] == 0

            short = await client.get("/api/users/search", params={"q": " "})
            assert short.status_code == 422

            page = await client.get(
                "/api/users/search",
                params={"q": "creator_", "limit": 1, "offset": 1},
            )
            assert page.status_code == 200
            assert page.json()["has_more"] is False
            assert len(page.json()["items"]) == 1
    finally:
        app.dependency_overrides.pop(get_db, None)
