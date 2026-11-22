"""Notification preference defaults and write-time suppression."""
from __future__ import annotations

import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Notification, NotificationPreference

NOTIFICATION_TYPES = {
    "forked": "有人基于你的创意进行了衍生",
    "collected": "有人收藏了你的创意",
    "spark_updated": "灵感状态已更新",
    "collab_published": "协作空间发布了最终成果",
}


async def notification_enabled(
    db: AsyncSession,
    user_id: uuid.UUID,
    notification_type: str,
) -> bool:
    preference = await db.scalar(
        select(NotificationPreference.enabled).where(
            NotificationPreference.user_id == user_id,
            NotificationPreference.notification_type == notification_type,
        )
    )
    # No row means the legacy-compatible default: enabled.
    return preference is not False


async def add_notification_if_enabled(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    notification_type: str,
    content: str,
    idea_id: uuid.UUID | None = None,
    actor_id: uuid.UUID | None = None,
) -> Notification | None:
    if not await notification_enabled(db, user_id, notification_type):
        return None
    notification = Notification(
        user_id=user_id,
        type=notification_type,
        content=content[:200],
        idea_id=idea_id,
        actor_id=actor_id,
    )
    db.add(notification)
    return notification
