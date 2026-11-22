"""End-to-end HTTP contract for private collaboration through public attribution."""

from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from deps import get_current_user, get_db, get_optional_user
from main import app
from models import User, Idea
from routers import ideas as ideas_router
from routers import idea_versions as versions_router


async def _user(db, username):
    user = User(username=username, password_hash="test-hash", bio="")
    db.add(user)
    await db.flush()
    return user


@pytest.mark.asyncio
async def test_private_collaboration_to_published_public_attribution_http_flow(
    db_session, monkeypatch
):
    owner = await _user(db_session, "e2e_collab_owner")
    collaborator = await _user(db_session, "e2e_collab_author")
    idea = Idea(
        content="一个尚未公开的校园创意",
        color_hex="#123456",
        source="ugc",
        author_id=owner.id,
        border_style="gold-thin",
        publication_status="draft",
        visibility="private",
    )
    db_session.add(idea)
    await db_session.commit()

    async def allow_audit(*args, **kwargs):
        return True, ""

    async def noop(*args, **kwargs):
        return None

    monkeypatch.setattr(ideas_router, "audit_content", allow_audit)
    monkeypatch.setattr(ideas_router, "write_audit_log", noop)
    monkeypatch.setattr(versions_router, "audit_content", allow_audit)
    monkeypatch.setattr(versions_router, "write_audit_log", noop)
    monkeypatch.setattr(ideas_router.cache, "delete", noop)
    monkeypatch.setattr(ideas_router.cache, "delete_pattern", noop)

    active_user = {"value": owner}

    async def override_db():
        yield db_session

    async def override_user():
        return active_user["value"]

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_optional_user] = override_user

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            # Owner invites a contributor; pending invitations grant no access.
            invite_response = await client.post(
                f"/api/ideas/{idea.id}/invites",
                json={"user_id": str(collaborator.id), "role": "contributor"},
            )
            assert invite_response.status_code == 201
            invite_id = invite_response.json()["invite_id"]

            active_user["value"] = collaborator
            inbox = await client.get("/api/ideas/invites/inbox")
            assert inbox.status_code == 200
            assert inbox.json()["items"][0]["idea_id"] == str(idea.id)

            pending_detail = await client.get(f"/api/ideas/{idea.id}")
            assert pending_detail.status_code == 404

            accepted = await client.post(
                f"/api/ideas/{idea.id}/invites/{invite_id}/accept"
            )
            assert accepted.status_code == 200
            assert accepted.json()["accepted"] is True

            accepted_detail = await client.get(f"/api/ideas/{idea.id}")
            assert accepted_detail.status_code == 200
            assert accepted_detail.json()["access_role"] == "contributor"

            submitted = await client.post(
                f"/api/ideas/{idea.id}/contributions",
                json={
                    "content": "增加校园社团协作场景",
                    "note": "补充目标用户和落地方式",
                },
            )
            assert submitted.status_code == 201
            contribution_id = submitted.json()["id"]

            updated = await client.patch(
                f"/api/ideas/{idea.id}/contributions/{contribution_id}",
                json={
                    "content": "增加校园社团与课程项目协作场景",
                    "note": "修订后的建议",
                },
            )
            assert updated.status_code == 200

            # Viewer role cannot submit contributions.
            viewer = await _user(db_session, "e2e_collab_viewer")
            active_user["value"] = owner
            viewer_invite = await client.post(
                f"/api/ideas/{idea.id}/invites",
                json={"user_id": str(viewer.id), "role": "viewer"},
            )
            assert viewer_invite.status_code == 201
            active_user["value"] = viewer
            viewer_accept = await client.post(
                f"/api/ideas/{idea.id}/invites/{viewer_invite.json()['invite_id']}/accept"
            )
            assert viewer_accept.status_code == 200
            viewer_submit = await client.post(
                f"/api/ideas/{idea.id}/contributions",
                json={"content": "viewer 不应提交"},
            )
            assert viewer_submit.status_code == 403

            # Owner reviews and accepts the collaborator's contribution.
            active_user["value"] = owner
            contributions = await client.get(
                f"/api/ideas/{idea.id}/contributions"
            )
            assert contributions.status_code == 200
            assert contributions.json()["items"][0]["status"] == "submitted"

            reviewed = await client.post(
                f"/api/ideas/{idea.id}/contributions/{contribution_id}/review",
                json={"decision": "accepted", "review_note": "采纳"},
            )
            assert reviewed.status_code == 200
            assert reviewed.json()["status"] == "accepted"

            # Explicitly publish the Idea, then publish a new version so it belongs
            # to the public era and can appear on the public timeline.
            published_idea = await client.post(
                f"/api/ideas/{idea.id}/publish",
                json={
                    "visibility": "public",
                    "license_code": "attribution_adaptation",
                    "license_version": "v1",
                    "allow_fork": True,
                    "confirm_terms": True,
                },
            )
            assert published_idea.status_code == 200
            public_since = datetime.fromisoformat(
                published_idea.json()["created_at"].replace("Z", "+00:00")
            )
            assert published_idea.json()["visibility"] == "public"

            draft = await client.post(
                f"/api/ideas/{idea.id}/versions/drafts",
                json={
                    "content": "加入校园社团与课程项目协作场景后的创意",
                    "change_summary": "采纳协作者的校园场景建议",
                    "contribution_ids": [contribution_id],
                },
            )
            assert draft.status_code == 201
            version_id = draft.json()["id"]

            version_published = await client.post(
                f"/api/ideas/{idea.id}/versions/{version_id}/publish"
            )
            assert version_published.status_code == 200
            assert version_published.json()["published"] is True
            assert version_published.json()["version"]["attributions"][0][
                "content"
            ] == "增加校园社团与课程项目协作场景"

            # Contributor's private collaboration feed links the accepted
            # contribution to the published version and frozen attribution.
            active_user["value"] = collaborator
            contribution_feed = await client.get(
                f"/api/ideas/{idea.id}/contributions"
            )
            assert contribution_feed.status_code == 200
            linked = contribution_feed.json()["items"][0]
            assert linked["published_version"]["id"] == version_id
            assert linked["attribution_content_snapshot"] == (
                "增加校园社团与课程项目协作场景"
            )
            assert linked["attribution_author_name"] == collaborator.username

            # Anonymous public timeline exposes only the published public-era
            # version and the frozen attribution snapshot.
            active_user["value"] = None
            public_timeline = await client.get(
                f"/api/ideas/{idea.id}/versions/public"
            )
            assert public_timeline.status_code == 200
            timeline_item = public_timeline.json()["items"][0]
            assert timeline_item["id"] == version_id
            assert timeline_item["attributions"][0]["author_name"] == (
                collaborator.username
            )
            assert timeline_item["attributions"][0]["content"] == (
                "增加校园社团与课程项目协作场景"
            )

    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_optional_user, None)
