"""通知路由"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from deps import get_db, get_current_user
from models import User, Notification, Idea
from services.idea_access import can_view_idea
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
    rows = result.scalars().all()
    # Notifications can outlive the access grant that originally exposed an Idea.
    # Re-check access at read time to avoid disclosing private content after revocation.
    idea_ids = {n.idea_id for n in rows if n.idea_id is not None}
    ideas_result = await db.execute(select(Idea).where(Idea.id.in_(idea_ids))) if idea_ids else None
    ideas_by_id = {
        idea.id: idea for idea in (ideas_result.scalars().all() if ideas_result else [])
    }
    visible_rows = []
    for notification in rows:
        if notification.idea_id is None:
            visible_rows.append(notification)
            continue
        idea = ideas_by_id.get(notification.idea_id)
        if idea is not None and await can_view_idea(db, idea, user.id):
            visible_rows.append(notification)

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
        for n in visible_rows
    ]
    unread_count = sum(1 for n in visible_rows if not n.read)

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
    # N5: SQLAlchemy Result 必有 rowcount，移除冗余 hasattr 兜底
    marked = result.rowcount or 0
    return MarkReadResponse(marked_read=marked)
