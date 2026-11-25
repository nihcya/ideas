from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from models import User, Idea, Notification
from routers.ideas import publish_idea
from schemas.idea import IdeaPublishRequest
from services.cache import cache
from services.idea_access import can_derive_from_idea
from services.legacy_license_transition import process_legacy_license_deadlines


async def _user(db, username):
    user = User(username=username, password_hash="test-hash", bio="")
    db.add(user)
    await db.flush()
    return user


async def _legacy_idea(db, author, due_at, *, notified_at=None):
    idea = Idea(
        content="历史公开创意",
        color_hex="#123456",
        source="ugc",
        author_id=author.id,
        border_style="gold-thin",
        status="active",
        publication_status="published",
        visibility="public",
        license_code="attribution",
        license_version="v1",
        allow_fork=True,
        is_forkable=True,
        legacy_license_review_status="pending",
        legacy_license_review_due_at=due_at,
        legacy_license_review_notified_at=notified_at,
    )
    db.add(idea)
    await db.flush()
    return idea


@pytest.mark.asyncio
async def test_daily_transition_sends_one_reminder_and_expires_overdue_ideas(db_session, monkeypatch):
    author = await _user(db_session, "legacy_transition_author")
    now = datetime.now(timezone.utc)
    due_soon = await _legacy_idea(db_session, author, now + timedelta(days=5))
    overdue = await _legacy_idea(db_session, author, now - timedelta(days=1))
    not_due = await _legacy_idea(db_session, author, now + timedelta(days=30))
    async def noop(*args, **kwargs):
        return None
    monkeypatch.setattr(cache, "delete_pattern", noop)
    monkeypatch.setattr(cache, "delete", noop)
    await db_session.commit()

    result = await process_legacy_license_deadlines(db_session, now=now)
    assert result == {"reminders_sent": 1, "expired": 1}

    await db_session.refresh(due_soon)
    await db_session.refresh(overdue)
    await db_session.refresh(not_due)
    assert due_soon.legacy_license_review_status == "pending"
    assert due_soon.legacy_license_review_notified_at is not None
    assert overdue.legacy_license_review_status == "expired"
    assert overdue.allow_fork is False
    assert overdue.is_forkable is False
    assert not_due.legacy_license_review_status == "pending"

    reminders = (await db_session.execute(
        select(Notification).where(
            Notification.user_id == author.id,
            Notification.type == "legacy_license_reminder",
        )
    )).scalars().all()
    assert len(reminders) == 1
    assert reminders[0].idea_id == due_soon.id
    assert await can_derive_from_idea(db_session, overdue, author.id) is False

    second_run = await process_legacy_license_deadlines(
        db_session, now=now + timedelta(days=1)
    )
    assert second_run["reminders_sent"] == 0
    assert second_run["expired"] == 0


@pytest.mark.asyncio
async def test_publish_cannot_reenable_forking_after_legacy_deadline(db_session):
    author = await _user(db_session, "legacy_publish_author")
    idea = await _legacy_idea(
        db_session,
        author,
        datetime.now(timezone.utc) - timedelta(days=1),
    )
    await db_session.commit()

    with pytest.raises(HTTPException) as exc:
        await publish_idea(
            idea.id,
            IdeaPublishRequest(
                visibility="public",
                license_code="attribution",
                allow_fork=True,
                confirm_terms=True,
            ),
            db_session,
            author,
        )
    assert exc.value.status_code == 422
    await db_session.refresh(idea)
    assert idea.legacy_license_review_status == "expired"
    assert idea.allow_fork is False
    assert idea.is_forkable is False
