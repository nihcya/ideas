"""User reports and admin moderation queue."""
import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from deps import get_db, get_current_user
from models import User, Idea, IdeaReport, SecurityEvent
from schemas.report import IdeaReportCreate, IdeaReportReview
from services.admin_access import is_admin_user
from services.idea_access import can_view_idea
from services.cache import cache, key_idea_detail
from services.rate_limit import limiter, DEFAULT_LIMIT

router = APIRouter(prefix="/reports", tags=["reports"])


def _admin_required(user: User):
    if not is_admin_user(user):
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "ADMIN_REQUIRED", "message": "需要管理员权限"}},
        )


@router.post("", status_code=201)
@limiter.limit(DEFAULT_LIMIT)
async def create_idea_report(
    request: Request,
    payload: IdeaReportCreate = Body(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        idea_id = uuid.UUID(payload.idea_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="idea_id 格式不正确")

    idea = await db.get(Idea, idea_id)
    if idea is None or not await can_view_idea(db, idea, user.id):
        raise HTTPException(status_code=404, detail="创意不存在或无权访问")
    existing = await db.scalar(
        select(IdeaReport.id).where(
            IdeaReport.idea_id == idea_id,
            IdeaReport.reporter_id == user.id,
            IdeaReport.status.in_(["pending", "in_review"]),
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail={"error": {"code": "REPORT_ALREADY_OPEN", "message": "你已经提交过该创意的待处理举报"}},
        )

    report = IdeaReport(
        idea_id=idea_id,
        reporter_id=user.id,
        reason=payload.reason,
        description=payload.description,
        status="pending",
    )
    db.add(report)
    db.add(SecurityEvent(
        action="idea_report_submitted",
        user_id=user.id,
        username=user.username,
        result="success",
        reason=f"idea_id={idea_id}; reason={payload.reason}",
    ))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        # The partial unique index serializes simultaneous submissions. Re-check
        # after rollback so a concurrent winner becomes the same stable 409 contract.
        existing = await db.scalar(
            select(IdeaReport.id).where(
                IdeaReport.idea_id == idea_id,
                IdeaReport.reporter_id == user.id,
                IdeaReport.status.in_(["pending", "in_review"]),
            )
        )
        if existing is not None:
            raise HTTPException(
                status_code=409,
                detail={"error": {"code": "REPORT_ALREADY_OPEN", "message": "你已经提交过该创意的待处理举报"}},
            )
        raise
    return {"id": str(report.id), "status": report.status}


@router.get("/admin")
@limiter.limit(DEFAULT_LIMIT)
async def list_admin_reports(
    request: Request,
    status_filter: Literal["pending", "in_review", "resolved", "dismissed"] | None = Query(None, alias="status"),
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _admin_required(user)
    query = (
        select(IdeaReport, Idea.content, User.username)
        .join(Idea, Idea.id == IdeaReport.idea_id)
        .join(User, User.id == IdeaReport.reporter_id)
    )
    if status_filter:
        query = query.where(IdeaReport.status == status_filter)
    query = query.order_by(IdeaReport.created_at.asc()).offset(offset).limit(limit + 1)
    rows = (await db.execute(query)).all()
    has_more = len(rows) > limit
    return {
        "items": [
            {
                "id": str(row.IdeaReport.id),
                "idea_id": str(row.IdeaReport.idea_id),
                "idea_content": row.content,
                "reporter_id": str(row.IdeaReport.reporter_id),
                "reporter_username": row.username,
                "reason": row.IdeaReport.reason,
                "description": row.IdeaReport.description,
                "status": row.IdeaReport.status,
                "resolution_note": row.IdeaReport.resolution_note,
                "action_taken": row.IdeaReport.action_taken,
                "created_at": row.IdeaReport.created_at,
                "reviewed_at": row.IdeaReport.reviewed_at,
            }
            for row in rows[:limit]
        ],
        "limit": limit,
        "offset": offset,
        "has_more": has_more,
    }


@router.post("/admin/{report_id}/review")
@limiter.limit(DEFAULT_LIMIT)
async def review_idea_report(
    request: Request,
    report_id: str,
    payload: IdeaReportReview = Body(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _admin_required(user)
    try:
        report_uuid = uuid.UUID(report_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="举报记录不存在")
    report = await db.scalar(
        select(IdeaReport).where(IdeaReport.id == report_uuid).with_for_update()
    )
    if report is None:
        raise HTTPException(status_code=404, detail="举报记录不存在")
    if report.status in ("resolved", "dismissed"):
        raise HTTPException(status_code=409, detail="该举报已完成处理")
    if payload.hide_idea and payload.status != "resolved":
        raise HTTPException(status_code=422, detail="只有完成处理时才能隐藏创意")

    idea = await db.scalar(
        select(Idea).where(Idea.id == report.idea_id).with_for_update()
    )
    if idea is None:
        raise HTTPException(status_code=404, detail="被举报创意不存在")

    if payload.hide_idea:
        idea.publication_status = "draft"
        idea.visibility = "private"
        idea.allow_fork = False
        idea.is_forkable = False
        report.action_taken = "hidden"
        await cache.delete_pattern("explore:v3:*")
        await cache.delete(key_idea_detail(str(idea.id)))
    else:
        report.action_taken = "none"

    report.status = payload.status
    report.reviewed_by = user.id
    report.reviewed_at = datetime.now(timezone.utc)
    report.resolution_note = payload.resolution_note
    db.add(SecurityEvent(
        action="idea_report_reviewed",
        user_id=user.id,
        username=user.username,
        result="success",
        reason=f"report_id={report.id}; status={payload.status}; action={report.action_taken}",
    ))
    await db.commit()
    return {
        "id": str(report.id),
        "status": report.status,
        "action_taken": report.action_taken,
        "idea_hidden": payload.hide_idea,
    }
