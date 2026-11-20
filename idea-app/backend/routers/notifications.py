"""通知路由"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select, update, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from deps import get_db, get_current_user
from models import User, Notification, Idea, IdeaAccessGrant
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
    # Apply resource visibility in SQL before pagination so hidden rows cannot
    # create short pages or leak ordering/position information.
    visible_linked_idea = select(Idea.id).where(
        Idea.id == Notification.idea_id,
        or_(
            Idea.author_id == user.id,
            and_(
                Idea.publication_status == "published",
                Idea.visibility == "public",
                Idea.status == "active",
            ),
            select(IdeaAccessGrant.id).where(
                IdeaAccessGrant.idea_id == Idea.id,
                IdeaAccessGrant.user_id == user.id,
                IdeaAccessGrant.status == "accepted",
            ).exists(),
        ),
    ).exists()
    visible_notification = or_(
        Notification.idea_id.is_(None),
        visible_linked_idea,
    )

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
