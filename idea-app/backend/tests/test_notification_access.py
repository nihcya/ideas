import pytest
from sqlalchemy import select, update, func

from models import User, Idea, IdeaAccessGrant, Notification
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


async def _notification(db, recipient_id, idea_id, content):
    notification = Notification(
        user_id=recipient_id,
        type="forked",
        content=content,
        idea_id=idea_id,
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

    visible = await _notification(db_session, recipient.id, public_idea.id, "public event")
    hidden = await _notification(db_session, recipient.id, private_idea.id, "private event")

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
