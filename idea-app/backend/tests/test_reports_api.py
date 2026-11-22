import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from config import settings
from deps import get_current_user, get_db
from main import app
from models import User, Idea, IdeaReport


async def _user(db, username):
    user = User(username=username, password_hash="test-hash", bio="")
    db.add(user)
    await db.flush()
    return user


async def _public_idea(db, owner):
    idea = Idea(
        content="需要社区治理的公开创意",
        color_hex="#123456",
        source="ugc",
        author_id=owner.id,
        border_style="gold-thin",
        status="active",
        publication_status="published",
        visibility="public",
        license_code="attribution",
        license_version="v1",
        allow_fork=True,
        is_forkable=True,
        legacy_license_review_status="not_required",
    )
    db.add(idea)
    await db.flush()
    return idea


@pytest.mark.asyncio
async def test_report_submission_admin_review_and_hide_public_idea(db_session, monkeypatch):
    owner = await _user(db_session, "report_idea_owner")
    reporter = await _user(db_session, "report_submitter")
    admin = await _user(db_session, "report_moderator")
    idea = await _public_idea(db_session, owner)
    await db_session.commit()

    active = {"user": reporter}

    async def override_db():
        yield db_session

    async def override_user():
        return active["user"]

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    monkeypatch.setattr(settings, "admin_user_ids", "")
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
            submitted = await client.post(
                "/api/reports",
                json={
                    "idea_id": str(idea.id),
                    "reason": "copyright",
                    "description": "疑似未经授权使用了第三方作品",
                },
            )
            assert submitted.status_code == 201
            report_id = submitted.json()["id"]

            duplicate = await client.post(
                "/api/reports",
                json={"idea_id": str(idea.id), "reason": "spam"},
            )
            assert duplicate.status_code == 409

            denied = await client.get("/api/reports/admin")
            assert denied.status_code == 403

            monkeypatch.setattr(settings, "admin_user_ids", str(admin.id))
            active["user"] = admin
            queue = await client.get("/api/reports/admin", params={"status": "pending"})
            assert queue.status_code == 200
            assert queue.json()["items"][0]["id"] == report_id
            assert queue.json()["items"][0]["reporter_username"] == reporter.username

            reviewed = await client.post(
                f"/api/reports/admin/{report_id}/review",
                json={
                    "status": "resolved",
                    "hide_idea": True,
                    "resolution_note": "经核查，先隐藏公开内容并等待权利人补充材料",
                },
            )
            assert reviewed.status_code == 200
            assert reviewed.json()["action_taken"] == "hidden"
            assert reviewed.json()["idea_hidden"] is True

            row = await db_session.get(Idea, idea.id)
            report = await db_session.get(IdeaReport, report_id)
            assert row.visibility == "private"
            assert row.publication_status == "draft"
            assert row.allow_fork is False
            assert report.status == "resolved"
            assert report.reviewed_by == admin.id
            assert report.action_taken == "hidden"

            repeated = await client.post(
                f"/api/reports/admin/{report_id}/review",
                json={"status": "dismissed"},
            )
            assert repeated.status_code == 409
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
