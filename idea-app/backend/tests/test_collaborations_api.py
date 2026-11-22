"""HTTP contracts for first-class asynchronous collaboration workspaces."""
import pytest
from httpx import ASGITransport, AsyncClient

from deps import get_current_user, get_db
from main import app
from models import User, Idea


async def _user(db, username):
    user = User(username=username, password_hash="test-hash", bio="")
    db.add(user)
    await db.flush()
    return user


@pytest.mark.asyncio
async def test_workspace_invitation_does_not_grant_private_source_idea_access(db_session):
    owner = await _user(db_session, "ws_owner")
    contributor = await _user(db_session, "ws_contrib")
    viewer = await _user(db_session, "ws_viewer")
    private_source = Idea(
        content="作者的私有来源创意",
        color_hex="#123456",
        source="ugc",
        author_id=owner.id,
        border_style="gold-thin",
        publication_status="draft",
        visibility="private",
    )
    db_session.add(private_source)
    await db_session.commit()

    active = {"user": owner}

    async def override_db():
        yield db_session

    async def override_user():
        return active["user"]

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
            created = await client.post("/api/collaborations", json={
                "title": "校园创意共创",
                "description": "异步补充方案",
                "source_idea_ids": [str(private_source.id)],
            })
            assert created.status_code == 201
            workspace_id = created.json()["id"]

            invite = await client.post(f"/api/collaborations/{workspace_id}/members", json={
                "user_id": str(contributor.id), "role": "contributor",
            })
            assert invite.status_code == 201

            active["user"] = contributor
            inbox = await client.get("/api/collaborations/invitations/inbox")
            assert inbox.status_code == 200
            assert inbox.json()["items"][0]["collaboration_id"] == workspace_id
            pending_read = await client.get(f"/api/collaborations/{workspace_id}")
            assert pending_read.status_code == 404
            pending_source_read = await client.get(f"/api/ideas/{private_source.id}")
            assert pending_source_read.status_code == 404

            accepted = await client.post(f"/api/collaborations/{workspace_id}/accept")
            assert accepted.status_code == 200
            workspace = await client.get(f"/api/collaborations/{workspace_id}")
            assert workspace.status_code == 200
            source = workspace.json()["sources"][0]
            assert source["accessible"] is False
            assert str(private_source.id) not in source["source_ref"]
            assert "rights_snapshot" not in source
            assert str(private_source.id) not in workspace.text

            submitted = await client.post(f"/api/collaborations/{workspace_id}/contributions", json={
                "content": "增加社团协作场景",
                "contribution_type": "research",
                "source_idea_id": None,
            })
            assert submitted.status_code == 201

            active["user"] = viewer
            viewer_invite = await client.post(f"/api/collaborations/{workspace_id}/members", json={
                "user_id": str(viewer.id), "role": "viewer",
            })
            assert viewer_invite.status_code == 404

            active["user"] = owner
            invite_viewer = await client.post(f"/api/collaborations/{workspace_id}/members", json={
                "user_id": str(viewer.id), "role": "viewer",
            })
            assert invite_viewer.status_code == 201
            active["user"] = viewer
            assert (await client.post(f"/api/collaborations/{workspace_id}/accept")).status_code == 200
            denied = await client.post(f"/api/collaborations/{workspace_id}/contributions", json={
                "content": "viewer 不可提交",
            })
            assert denied.status_code == 404

            active["user"] = owner
            owner_view = await client.get(f"/api/collaborations/{workspace_id}")
            assert owner_view.status_code == 200
            assert len(owner_view.json()["contributions"]) == 1
            assert owner_view.json()["contributions"][0]["status"] == "submitted"

            revoked = await client.delete(f"/api/collaborations/{workspace_id}/members/{contributor.id}")
            assert revoked.status_code == 200
            active["user"] = contributor
            revoked_workspace = await client.get(f"/api/collaborations/{workspace_id}")
            assert revoked_workspace.status_code == 404
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
