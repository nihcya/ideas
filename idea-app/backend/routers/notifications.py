"""通知路由"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from deps import get_db, get_current_user
from models import User, Notification
from schemas.notification import (
    NotificationItem, NotificationsResponse,
    MarkReadRequest, MarkReadResponse,
)
from services.rate_limit import limiter, DEFAULT_LIMIT

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationsResponse)
@limiter.limit(DEFAULT_LIMIT)
async def get_notifications(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
        .limit(limit).offset(offset)
    )
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
        for n in result.scalars().all()
    ]

    unread_result = await db.execute(
        select(func.count()).select_from(Notification).where(
            Notification.user_id == user.id, Notification.read == False
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
            ids.append(__import__("uuid").UUID(nid))
        except ValueError:
            continue

    result = await db.execute(
        update(Notification)
        .where(
            Notification.user_id == user.id,
            Notification.id.in_(ids),
            Notification.read == False,
        )
        .values(read=True)
    )
    await db.commit()
    marked = result.rowcount if hasattr(result, "rowcount") else 0
    return MarkReadResponse(marked_read=marked)
