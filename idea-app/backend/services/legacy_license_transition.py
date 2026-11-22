"""Daily transition job for historical public Idea authorization."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models import Idea
from services.cache import cache, key_idea_detail
from services.notification_preferences import add_notification_if_enabled


async def process_legacy_license_deadlines(
    db: AsyncSession,
    *,
    now: datetime | None = None,
    reminder_window_days: int = 7,
) -> dict[str, int]:
    """Send one reminder in the final week and expire overdue legacy rights.

    Expiry never deletes/unpublishes historical content. It only prevents further
    derivation until the creator explicitly completes a valid rights review.
    """
    current = now or datetime.now(timezone.utc)
    reminder_cutoff = current + timedelta(days=reminder_window_days)
    reminders = (await db.execute(
        select(Idea).where(
            Idea.legacy_license_review_status == "pending",
            Idea.legacy_license_review_due_at > current,
            Idea.legacy_license_review_due_at <= reminder_cutoff,
            Idea.legacy_license_review_notified_at.is_(None),
            Idea.author_id.is_not(None),
        ).with_for_update(skip_locked=True)
    )).scalars().all()

    for idea in reminders:
        await add_notification_if_enabled(
            db,
            user_id=idea.author_id,
            notification_type="legacy_license_reminder",
            content="你的历史公开创意授权补充期限将在 7 天内结束，请检查并确认授权条款。",
            idea_id=idea.id,
        )
        idea.legacy_license_review_notified_at = current

    expired_rows = (await db.execute(
        select(Idea.id).where(
            Idea.legacy_license_review_status == "pending",
            Idea.legacy_license_review_due_at <= current,
        )
    )).scalars().all()
    if expired_rows:
        await db.execute(
            update(Idea)
            .where(
                Idea.id.in_(expired_rows),
                Idea.legacy_license_review_status == "pending",
            )
            .values(
                legacy_license_review_status="expired",
                allow_fork=False,
                is_forkable=False,
            )
        )
        await cache.delete_pattern("explore:v3:*")
        for idea_id in expired_rows:
            await cache.delete(key_idea_detail(str(idea_id)))

    await db.commit()
    return {"reminders_sent": len(reminders), "expired": len(expired_rows)}
