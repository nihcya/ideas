"""通知路由"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from deps import get_db, get_current_user
from models import User, Notification, NotificationPreference
from services.notification_access import visible_notification_predicate
from schemas.notification import (
    NotificationItem, NotificationsResponse,
    MarkReadRequest, MarkReadResponse,
)
from schemas.notification_preference import (
    NotificationPreferenceItem,
    NotificationPreferencesResponse,
    NotificationPreferencesUpdateRequest,
)
from services.notification_preferences import NOTIFICATION_TYPES
from services.rate_limit import limiter, DEFAULT_LIMIT

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/preferences", response_model=NotificationPreferencesResponse)
@limiter.limit(DEFAULT_LIMIT)
async def get_notification_preferences(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(NotificationPreference).where(NotificationPreference.user_id == user.id)
    )
    saved = {row.notification_type: row.enabled for row in result.scalars().all()}
    return NotificationPreferencesResponse(
        items=[
            NotificationPreferenceItem(
                notification_type=notification_type,
                enabled=saved.get(notification_type, True),
            )
            for notification_type in NOTIFICATION_TYPES
        ]
    )


@router.put("/preferences", response_model=NotificationPreferencesResponse)
@limiter.limit(DEFAULT_LIMIT)
async def update_notification_preferences(
    request: Request,
    payload: NotificationPreferencesUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    unknown = [
        item.notification_type for item in payload.items
        if item.notification_type not in NOTIFICATION_TYPES
    ]
    if unknown:
        raise HTTPException(
            status_code=422,
            detail={"error": {"code": "UNKNOWN_NOTIFICATION_TYPE", "message": "包含未知通知类型"}},
        )
    for item in payload.items:
        row = await db.scalar(
            select(NotificationPreference).where(
                NotificationPreference.user_id == user.id,
                NotificationPreference.notification_type == item.notification_type,
            ).with_for_update()
        )
        if row is None:
            db.add(NotificationPreference(
                user_id=user.id,
                notification_type=item.notification_type,
                enabled=item.enabled,
            ))
        else:
            row.enabled = item.enabled
    await db.commit()
    result = await db.execute(
        select(NotificationPreference).where(NotificationPreference.user_id == user.id)
    )
    saved = {row.notification_type: row.enabled for row in result.scalars().all()}
    return NotificationPreferencesResponse(
        items=[
            NotificationPreferenceItem(
                notification_type=notification_type,
                enabled=saved.get(notification_type, True),
            )
            for notification_type in NOTIFICATION_TYPES
        ]
    )


@router.get("", response_model=NotificationsResponse)
@limiter.limit(DEFAULT_LIMIT)
async def get_notifications(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Apply resource visibility in SQL before pagination so hidden rows cannot
    # create short pages or leak ordering/position information.
    visible_notification = visible_notification_predicate(user.id)

    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == user.id, visible_notification)
        .order_by(Notification.created_at.desc())
        .limit(limit).offset(offset)
    )
    rows = result.scalars().all()
    notifications = [
        NotificationItem(
            id=str(n.id),
            type=n.type,
            content=n.content,
            idea_id=str(n.idea_id) if n.idea_id else None,
            actor_id=str(n.actor_id) if n.actor_id else None,
            created_at=n.created_at,
            read=n.read,
        )
        for n in rows
    ]
    unread_result = await db.execute(
        select(func.count()).select_from(Notification).where(
            Notification.user_id == user.id,
            Notification.read == False,
            visible_notification,
        )
    )
    unread_count = unread_result.scalar() or 0

    return NotificationsResponse(
        notifications=notifications,
        unread_count=unread_count,
    )


@router.post("/read", response_model=MarkReadResponse)
@limiter.limit(DEFAULT_LIMIT)
async def mark_read(
    request: Request,
    req: MarkReadRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not req.notification_ids:
        return MarkReadResponse(marked_read=0)

    ids = []
    for nid in req.notification_ids:
        try:
            ids.append(uuid.UUID(nid))
        except ValueError:
            continue

    # Mark-read must enforce the same current resource ACL as list retrieval.
    # Otherwise a stale notification ID could still be operated on after access
    # to its private Idea has been revoked.
    visible_notification = visible_notification_predicate(user.id)

    result = await db.execute(
        update(Notification)
        .where(
            Notification.user_id == user.id,
            Notification.id.in_(ids),
            Notification.read == False,
            visible_notification,
        )
        .values(read=True)
    )
    await db.commit()
    # N5: SQLAlchemy Result 必有 rowcount，移除冗余 hasattr 兜底
    marked = result.rowcount or 0
    return MarkReadResponse(marked_read=marked)
