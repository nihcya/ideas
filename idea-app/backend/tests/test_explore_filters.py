"""Explore filtering, sorting, pagination and cache-key isolation."""
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from deps import get_db, get_optional_user
from main import app
from models import User, Idea
from routers import ideas as ideas_router


def _idea(owner_id, content, *, license_code, allow_fork, source, created_at, fork_count=0, last_fork_at=None, visibility="public", publication_status="published"):
    return Idea(
        content=content,
        color_hex="#123456",
        source=source,
        author_id=owner_id,
        border_style="gold-thin",
        status="active",
        publication_status=publication_status,
        visibility=visibility,
        license_code=license_code,
        license_version="v1",
        allow_fork=allow_fork,
        is_forkable=allow_fork,
        fork_count=fork_count,
        last_fork_at=last_fork_at,
        published_at=created_at if publication_status == "published" else None,
        created_at=created_at,
        legacy_license_review_status="not_required",
    )


@pytest.mark.asyncio
async def test_explore_filters_sort_and_recommended_pagination(db_session, monkeypatch):
    now = datetime.now(timezone.utc)
    owner = User(username="explore_filter_owner", password_hash="test-hash", bio="")
    db_session.add(owner)
    await db_session.flush()

    latest = _idea(
        owner.id, "公开创意甲", license_code="attribution", allow_fork=True,
        source="ugc", created_at=now, fork_count=5, last_fork_at=now - timedelta(days=1),
    )
    forked = _idea(
        owner.id, "公开创意乙", license_code="attribution_adaptation", allow_fork=True,
        source="collide", created_at=now - timedelta(days=2), fork_count=20,
        last_fork_at=now - timedelta(days=2),
    )
    restricted = _idea(
        owner.id, "公开创意丙", license_code="all_rights_reserved", allow_fork=False,
        source="fork", created_at=now - timedelta(days=3), fork_count=0,
    )
    private = _idea(
        owner.id, "私有创意绝不应出现在探索", license_code="custom", allow_fork=False,
        source="ugc", created_at=now, visibility="private", publication_status="draft",
    )
    db_session.add_all([latest, forked, restricted, private])
    await db_session.commit()

    active = {"user": None}

    async def override_db():
        yield db_session

    async def override_user():
        return active["user"]

    async def no_cache_get(*args, **kwargs):
        return None

    async def no_cache_set(*args, **kwargs):
        return None

    async def no_lock(*args, **kwargs):
        return "test-lock"

    async def no_wait(*args, **kwargs):
        return None

    async def no_release(*args, **kwargs):
        return None

    monkeypatch.setattr(ideas_router.cache, "get", no_cache_get)
    monkeypatch.setattr(ideas_router.cache, "set", no_cache_set)
    monkeypatch.setattr(ideas_router.cache, "acquire_lock", no_lock)
    monkeypatch.setattr(ideas_router.cache, "wait_for_cache", no_wait)
    monkeypatch.setattr(ideas_router.cache, "release_lock", no_release)

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_optional_user] = override_user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
            latest_response = await client.get(
                "/api/ideas/explore", params={"sort": "latest", "limit": 10}
            )
            assert latest_response.status_code == 200
            latest_ids = [item["id"] for item in latest_response.json()["circles"]]
            assert latest_ids == [str(latest.id), str(forked.id), str(restricted.id)]
            assert str(private.id) not in latest_ids

            license_response = await client.get(
                "/api/ideas/explore",
                params={"license_code": "attribution_adaptation", "sort": "latest"},
            )
            assert [item["id"] for item in license_response.json()["circles"]] == [str(forked.id)]

            allow_response = await client.get(
                "/api/ideas/explore", params={"allow_fork": "true", "sort": "latest"}
            )
            assert {item["id"] for item in allow_response.json()["circles"]} == {
                str(latest.id), str(forked.id)
            }

            source_response = await client.get(
                "/api/ideas/explore", params={"source": "fork", "sort": "latest"}
            )
            assert [item["id"] for item in source_response.json()["circles"]] == [str(restricted.id)]

            search_response = await client.get(
                "/api/ideas/explore", params={"q": "公开创意", "sort": "latest"}
            )
            assert len(search_response.json()["circles"]) == 3

            forked_sort = await client.get(
                "/api/ideas/explore", params={"sort": "forked", "limit": 10}
            )
            forked_ids = [item["id"] for item in forked_sort.json()["circles"]]
            assert forked_ids[:3] == [str(forked.id), str(latest.id), str(restricted.id)]

            first_page = await client.get(
                "/api/ideas/explore", params={"sort": "recommended", "limit": 1, "offset": 0}
            )
            second_page = await client.get(
                "/api/ideas/explore", params={"sort": "recommended", "limit": 1, "offset": 1}
            )
            first_id = first_page.json()["circles"][0]["id"]
            second_id = second_page.json()["circles"][0]["id"]
            assert first_id != second_id
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_optional_user, None)
