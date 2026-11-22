"""HTTP contracts for first-class asynchronous collaboration workspaces."""
import uuid
import pytest
from sqlalchemy import select
from httpx import ASGITransport, AsyncClient

from deps import get_current_user, get_db
from main import app
from models import (
    User, Idea, Collaboration, CollaborationContribution, ForkRelation,
    IdeaVersion, IdeaVersionContribution, IdeaContribution,
)
from routers import collaborations as collaborations_router


async def _user(db, username):
    user = User(username=username, password_hash="test-hash", bio="")
    db.add(user)
    await db.flush()
    return user


@pytest.mark.asyncio
async def test_workspace_invitation_does_not_grant_private_source_idea_access(db_session, monkeypatch):
    owner = await _user(db_session, "ws_owner")
    contributor = await _user(db_session, "ws_contrib")
    other_contributor = await _user(db_session, "ws_other")
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

    async def allow_audit(*args, **kwargs):
        return True, ""

    monkeypatch.setattr(collaborations_router, "audit_content", allow_audit)

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

            active["user"] = owner
            other_invite = await client.post(f"/api/collaborations/{workspace_id}/members", json={
                "user_id": str(other_contributor.id), "role": "contributor",
            })
            assert other_invite.status_code == 201
            active["user"] = other_contributor
            assert (await client.post(f"/api/collaborations/{workspace_id}/accept")).status_code == 200
            other_submission = await client.post(f"/api/collaborations/{workspace_id}/contributions", json={
                "content": "另一位成员的独立提案",
            })
            assert other_submission.status_code == 201

            active["user"] = contributor
            contributor_view = await client.get(f"/api/collaborations/{workspace_id}")
            assert contributor_view.status_code == 200
            assert [item["content"] for item in contributor_view.json()["contributions"]] == ["增加社团协作场景"]
            assert all(event["actor_id"] == str(contributor.id) for event in contributor_view.json()["events"])

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


@pytest.mark.asyncio
async def test_collaboration_publish_atomically_creates_idea_version_lineage_and_frozen_attribution(
    db_session, monkeypatch
):
    from datetime import datetime, timezone

    owner = await _user(db_session, "publish_owner")
    contributor = await _user(db_session, "publish_contrib")
    source = Idea(
        content="公开且允许改编的来源创意",
        color_hex="#123456",
        source="ugc",
        author_id=owner.id,
        border_style="gold-thin",
        publication_status="published",
        visibility="public",
        license_code="custom",
        license_text_snapshot="允许署名改编，需保留本授权说明",
        license_version="v1",
        allow_fork=True,
        is_forkable=True,
        published_at=datetime.now(timezone.utc),
        legacy_license_review_status="not_required",
    )
    db_session.add(source)
    await db_session.commit()

    async def allow_audit(*args, **kwargs):
        return True, ""

    async def noop(*args, **kwargs):
        return None

    monkeypatch.setattr(collaborations_router, "audit_content", allow_audit)
    monkeypatch.setattr(collaborations_router, "write_audit_log", noop)
    monkeypatch.setattr(collaborations_router.cache, "delete", noop)
    monkeypatch.setattr(collaborations_router.cache, "delete_pattern", noop)

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
                "title": "可发布的多人共创",
                "source_idea_ids": [str(source.id)],
            })
            assert created.status_code == 201
            workspace_id = created.json()["id"]

            invited = await client.post(f"/api/collaborations/{workspace_id}/members", json={
                "user_id": str(contributor.id), "role": "contributor",
            })
            assert invited.status_code == 201

            active["user"] = contributor
            assert (await client.post(f"/api/collaborations/{workspace_id}/accept")).status_code == 200
            proposal = await client.post(f"/api/collaborations/{workspace_id}/contributions", json={
                "content": "补充社区试点验证路径",
                "contribution_type": "research",
            })
            assert proposal.status_code == 201
            contribution_id = proposal.json()["id"]

            active["user"] = owner
            reviewed = await client.post(
                f"/api/collaborations/{workspace_id}/contributions/{contribution_id}/review",
                json={"decision": "accepted", "review_note": "采纳"},
            )
            assert reviewed.status_code == 200

            publish_payload = {
                "content": "面向社区的多人创意共创方案",
                "change_summary": "整合协作者研究建议",
                "visibility": "public",
                "license_code": "attribution_adaptation",
                "license_version": "v1",
                "allow_fork": True,
                "confirm_terms": True,
                "accepted_contribution_ids": [contribution_id],
            }
            missing_custom_ack = await client.post(
                f"/api/collaborations/{workspace_id}/publish", json=publish_payload
            )
            assert missing_custom_ack.status_code == 422
            assert missing_custom_ack.json()["detail"]["error"]["code"] == "CUSTOM_LICENSE_CONFIRMATION_REQUIRED"

            publish_payload["confirm_custom_licenses"] = True
            published = await client.post(f"/api/collaborations/{workspace_id}/publish", json=publish_payload)
            assert published.status_code == 201
            payload = published.json()
            output_id = payload["idea_id"]

            output = await db_session.get(Idea, uuid.UUID(output_id))
            assert output is not None
            assert output.publication_status == "published"
            assert output.visibility == "public"
            assert output.allow_fork is True

            version = await db_session.get(IdeaVersion, payload["version_id"])
            assert version is not None and version.status == "published"
            assert version.content_snapshot == output.content

            relation = (await db_session.execute(
                select(ForkRelation).where(ForkRelation.child_id == output.id)
            )).scalar_one()
            assert relation.parent_id == source.id
            assert relation.license_snapshot["rights_chain"][0]["license_code"] == "custom"
            assert relation.license_snapshot["custom_license_acknowledgement"]["acknowledged"] is True

            bridge = (await db_session.execute(
                select(IdeaContribution).where(
                    IdeaContribution.source_collaboration_contribution_id == uuid.UUID(contribution_id)
                )
            )).scalar_one()
            attribution = (await db_session.execute(
                select(IdeaVersionContribution).where(
                    IdeaVersionContribution.version_id == version.id,
                    IdeaVersionContribution.contribution_id == bridge.id,
                )
            )).scalar_one()
            assert attribution.author_id_snapshot == contributor.id
            assert attribution.author_name_snapshot == contributor.username
            assert attribution.content_snapshot == "补充社区试点验证路径"

            workspace = await db_session.get(Collaboration, uuid.UUID(workspace_id))
            assert workspace.status == "published"
            assert workspace.published_idea_id == output.id
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
