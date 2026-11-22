from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, update, func
from httpx import ASGITransport, AsyncClient

from models import (\n    User, Idea, IdeaAccessGrant, Notification, NotificationPreference,\n    Collaboration, CollaborationMember,\n)
from deps import get_current_user, get_db
from main import app
from services.notification_preferences import add_notification_if_enabled
from services.notification_access import visible_notification_predicate


async def _user(db, username):
    user = User(username=username, password_hash="test-hash", bio="")
    db.add(user)
    await db.flush()
    return user


async def _idea(db, author_id, **overrides):
    values = dict(
        content="通知权限测试",
        color_hex="#123456",
        source="ugc",
        author_id=author_id,
        border_style="none",
    )
    values.update(overrides)
    idea = Idea(**values)
    db.add(idea)
    await db.flush()
    return idea


async def _notification(db, recipient_id, idea_id, content, created_at):
    notification = Notification(
        user_id=recipient_id,
        type="forked",
        content=content,
        idea_id=idea_id,
        created_at=created_at,
    )
    db.add(notification)
    await db.flush()
    return notification


@pytest.mark.asyncio
async def test_notification_acl_filters_before_pagination_and_hides_revoked_invites(db_session):
    owner = await _user(db_session, "notification_owner")
    recipient = await _user(db_session, "notification_recipient")
    public_idea = await _idea(
        db_session,
        owner.id,
        publication_status="published",
        visibility="public",
    )
    private_idea = await _idea(
        db_session,
        owner.id,
        publication_status="published",
        visibility="private",
    )
    grant = IdeaAccessGrant(
        idea_id=private_idea.id,
        user_id=recipient.id,
        role="viewer",
        status="revoked",
        invited_by=owner.id,
    )
    db_session.add(grant)
    await db_session.flush()

    now = datetime.now(timezone.utc)
    visible = await _notification(db_session, recipient.id, public_idea.id, "public event", now)
    hidden = await _notification(db_session, recipient.id, private_idea.id, "private event", now + timedelta(seconds=1))

    predicate = visible_notification_predicate(recipient.id)
    page = await db_session.execute(
        select(Notification)
        .where(Notification.user_id == recipient.id, predicate)
        .order_by(Notification.created_at.desc())
        .limit(1)
    )
    page_rows = page.scalars().all()
    assert len(page_rows) == 1
    assert page_rows[0].id == visible.id

    unread = await db_session.execute(
        select(func.count()).select_from(Notification).where(
            Notification.user_id == recipient.id,
            Notification.read == False,
            predicate,
        )
    )
    assert unread.scalar_one() == 1

    mark_hidden = await db_session.execute(
        update(Notification)
        .where(
            Notification.user_id == recipient.id,
            Notification.id == hidden.id,
            Notification.read == False,
            predicate,
        )
        .values(read=True)
    )
    assert (mark_hidden.rowcount or 0) == 0

    mark_visible = await db_session.execute(
        update(Notification)
        .where(
            Notification.user_id == recipient.id,
            Notification.id == visible.id,
            Notification.read == False,
            predicate,
        )
        .values(read=True)
    )
    assert (mark_visible.rowcount or 0) == 1



@pytest.mark.asyncio
async def test_notification_preferences_filter_feed_and_suppress_future_writes(db_session):
    owner = await _user(db_session, "notification_pref_owner")
    recipient = await _user(db_session, "notification_pref_recipient")
    public_idea = await _idea(
        db_session,
        owner.id,
        publication_status="published",
        visibility="public",
    )
    disabled_notification = await _notification(
        db_session, recipient.id, public_idea.id, "旧的衍生通知", datetime.now(timezone.utc)
    )
    enabled_notification = Notification(
        user_id=recipient.id,
        type="collab_published",
        content="协作成果已发布",
        idea_id=public_idea.id,
    )
    db_session.add(enabled_notification)
    await db_session.commit()

    active = {"user": recipient}

    async def override_db():
        yield db_session

    async def override_user():
        return active["user"]

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
            defaults = await client.get("/api/notifications/preferences")
            assert defaults.status_code == 200
            assert all(item["enabled"] is True for item in defaults.json()["items"])

            updated = await client.put(
                "/api/notifications/preferences",
                json={"items": [{"notification_type": "forked", "enabled": False}]},
            )
            assert updated.status_code == 200
            saved = {item["notification_type"]: item["enabled"] for item in updated.json()["items"]}
            assert saved["forked"] is False
            assert saved["collab_published"] is True

            feed = await client.get("/api/notifications")
            assert feed.status_code == 200
            assert [item["id"] for item in feed.json()["notifications"]] == [str(enabled_notification.id)]
            assert feed.json()["unread_count"] == 1

            mark_disabled = await client.post(
                "/api/notifications/read",
                json={"notification_ids": [str(disabled_notification.id)]},
            )
            assert mark_disabled.status_code == 200
            assert mark_disabled.json()["marked_read"] == 0

            mark_enabled = await client.post(
                "/api/notifications/read",
                json={"notification_ids": [str(enabled_notification.id)]},
            )
            assert mark_enabled.status_code == 200
            assert mark_enabled.json()["marked_read"] == 1

        suppressed = await add_notification_if_enabled(
            db_session,
            user_id=recipient.id,
            notification_type="forked",
            content="用户已关闭的通知类型",
            idea_id=public_idea.id,
        )
        allowed = await add_notification_if_enabled(
            db_session,
            user_id=recipient.id,
            notification_type="collab_published",
            content="仍然启用的通知类型",
            idea_id=public_idea.id,
        )
        assert suppressed is None
        assert allowed is not None
        await db_session.commit()
        assert await db_session.scalar(
            select(func.count()).select_from(Notification).where(
                Notification.user_id == recipient.id,
                Notification.content == "用户已关闭的通知类型",
            )
        ) == 0
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)



@pytest.mark.asyncio
async def test_private_collaboration_notifications_follow_membership_acl(db_session):
    owner = await _user(db_session, "notification_collab_owner")
    pending_user = await _user(db_session, "notification_collab_pending")
    accepted_user = await _user(db_session, "notification_collab_accepted")
    outsider = await _user(db_session, "notification_collab_outsider")
    workspace = Collaboration(
        title="私有协作通知 ACL",
        owner_id=owner.id,
        status="draft",
        visibility="private",
    )
    db_session.add(workspace)
    await db_session.flush()
    db_session.add_all([
        CollaborationMember(
            collaboration_id=workspace.id,
            user_id=owner.id,
            role="owner",
            status="accepted",
            invited_by=owner.id,
        ),
        CollaborationMember(
            collaboration_id=workspace.id,
            user_id=pending_user.id,
            role="contributor",
            status="pending",
            invited_by=owner.id,
        ),
        CollaborationMember(
            collaboration_id=workspace.id,
            user_id=accepted_user.id,
            role="contributor",
            status="accepted",
            invited_by=owner.id,
        ),
    ])
    db_session.add_all([
        Notification(
            user_id=pending_user.id,
            type="collab_invited",
            content="协作邀请",
            collaboration_id=workspace.id,
        ),
        Notification(
            user_id=accepted_user.id,
            type="collab_published",
            content="私有协作成果",
            collaboration_id=workspace.id,
        ),
    ])
    await db_session.commit()

    pending_rows = (await db_session.execute(
        select(Notification).where(
            Notification.user_id == pending_user.id,
            visible_notification_predicate(pending_user.id),
        )
    )).scalars().all()
    accepted_rows = (await db_session.execute(
        select(Notification).where(
            Notification.user_id == accepted_user.id,
            visible_notification_predicate(accepted_user.id),
        )
    )).scalars().all()
    outsider_rows = (await db_session.execute(
        select(Notification).where(
            Notification.user_id == outsider.id,
            visible_notification_predicate(outsider.id),
        )
    )).scalars().all()
    assert [item.type for item in pending_rows] == ["collab_invited"]
    assert [item.type for item in accepted_rows] == ["collab_published"]
    assert outsider_rows == []

    pending_member = await db_session.scalar(select(CollaborationMember).where(
        CollaborationMember.collaboration_id == workspace.id,
        CollaborationMember.user_id == pending_user.id,
    ))
    pending_member.status = "declined"
    await db_session.commit()
    hidden_after_decline = (await db_session.execute(
        select(Notification).where(
            Notification.user_id == pending_user.id,
            visible_notification_predicate(pending_user.id),
        )
    )).scalars().all()
    assert hidden_after_decline == []
