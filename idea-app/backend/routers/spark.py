"""今日一点路由"""
from datetime import date, datetime, timezone
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from deps import get_db, get_current_user
from models import User, Idea, SparkQuestion, SparkDraft, SparkSubmission, VaultItem
from schemas.spark import (
    SparkTodayResponse, SparkDraftRequest, SparkDraftResponse,
    SparkSubmitRequest, SparkSubmitResponse,
)
from services.spark_service import (
    get_today_question, get_or_create_draft, has_submitted,
    get_expiry_for_today, is_today_expired,
)
from services.color_pool import random_color
from services.audit_service import audit_content
from config import settings

router = APIRouter(prefix="/spark", tags=["spark"])


@router.get("/today", response_model=SparkTodayResponse)
async def get_today(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if is_today_expired():
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail={"error": {"code": "SPARK_EXPIRED", "message": "今日题目已过期"}},
        )

    today_q = await get_today_question(db)
    if today_q is None:
        # 题库用完时回退到今日 + 30 天后第一题
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "今日无题目"}},
        )

    has_draft = False
    draft_result = await db.execute(
        select(SparkDraft).where(
            SparkDraft.user_id == user.id,
            SparkDraft.question_id == today_q.id,
        )
    )
    draft = draft_result.scalar_one_or_none()
    if draft and draft.content:
        has_draft = True

    submitted = await has_submitted(db, user.id, today_q.id)

    return SparkTodayResponse(
        date=today_q.date,
        question=today_q.question,
        type=today_q.type,
        duration_seconds=settings.spark_duration_seconds,
        has_draft=has_draft,
        submitted=submitted,
    )


@router.post("/draft", response_model=SparkDraftResponse)
async def save_draft(
    req: SparkDraftRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if is_today_expired():
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail={"error": {"code": "SPARK_EXPIRED", "message": "今日已过期"}},
        )

    today_q = await get_today_question(db)
    if today_q is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "今日无题目"}},
        )

    # 检查是否已提交
    if await has_submitted(db, user.id, today_q.id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": "ALREADY_EXISTS", "message": "今日已提交"}},
        )

    # 获取或创建草稿
    existing = await db.execute(
        select(SparkDraft).where(
            SparkDraft.user_id == user.id,
            SparkDraft.question_id == today_q.id,
        )
    )
    existing_draft = existing.scalar_one_or_none()
    is_first_save = existing_draft is None or not existing_draft.content

    draft = await get_or_create_draft(db, user.id, today_q.id)
    draft.content = req.content
    draft.expires_at = get_expiry_for_today()
    await db.commit()

    return SparkDraftResponse(
        saved=True,
        expires_at=get_expiry_for_today(),
        first_save=is_first_save,
    )


@router.post("/submit", response_model=SparkSubmitResponse, status_code=201)
async def submit(
    req: SparkSubmitRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if is_today_expired():
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail={"error": {"code": "SPARK_EXPIRED", "message": "今日已过期，不能补做"}},
        )

    today_q = await get_today_question(db)
    if today_q is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "今日无题目"}},
        )

    # 已提交过
    if await has_submitted(db, user.id, today_q.id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": "ALREADY_EXISTS", "message": "今日已提交过"}},
        )

    # 审核
    passed, reason = await audit_content(db, req.content)
    if not passed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "AUDIT_FAILED", "message": reason or "内容审核不通过"}},
        )

    color = random_color()
    new_idea = Idea(
        content=req.content,
        color_hex=color,
        source="today_spark",
        author_id=user.id,
        border_style="gold-thin",
        ai_assisted=False,
    )
    db.add(new_idea)
    await db.flush()

    # 入仓库
    vault_item = VaultItem(
        user_id=user.id,
        idea_id=new_idea.id,
        is_producer=True,
    )
    db.add(vault_item)

    # 记录提交
    submission = SparkSubmission(
        user_id=user.id,
        question_id=today_q.id,
        idea_id=new_idea.id,
    )
    db.add(submission)

    await db.commit()
    await db.refresh(new_idea)

    return SparkSubmitResponse(
        id=str(new_idea.id),
        source="today_spark",
        border_style="gold-thin",
        color_hex=new_idea.color_hex,
    )
