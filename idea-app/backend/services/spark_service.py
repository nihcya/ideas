"""今日一点服务"""
from datetime import date, datetime, timedelta, timezone
from typing import Optional
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import SparkQuestion, SparkDraft, SparkSubmission, Idea, User
from config import settings


async def get_today_question(db: AsyncSession, today: Optional[date] = None) -> Optional[SparkQuestion]:
    """获取今日题目。

    查询优先；若当日题目不存在，调用 AI 实时生成并写入数据库（兜底）。
    定时任务正常情况下会在 00:05 预生成，本兜底仅用于：
    - 定时任务失败
    - 服务首次启动且无历史题库
    - 时区/日期切换边界
    """
    if today is None:
        today = date.today()
    result = await db.execute(
        select(SparkQuestion).where(SparkQuestion.date == today)
    )
    q = result.scalar_one_or_none()
    if q is not None:
        return q

    # AI 兜底生成
    from services.spark_ai_service import generate_and_persist
    print(f"[spark] no question for {today}, generating via AI fallback")
    return await generate_and_persist(db, today)


def get_expiry_for_today() -> datetime:
    """今日 23:59:59 本地时间。"""
    now = datetime.now()
    end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=0)
    return end_of_day


def is_today_expired() -> bool:
    """是否已过期（超过今日23:59）。"""
    return datetime.now() > get_expiry_for_today()


async def get_or_create_draft(
    db: AsyncSession,
    user_id: uuid.UUID,
    question_id: uuid.UUID,
) -> SparkDraft:
    """获取或创建草稿。"""
    result = await db.execute(
        select(SparkDraft).where(
            SparkDraft.user_id == user_id,
            SparkDraft.question_id == question_id,
        )
    )
    draft = result.scalar_one_or_none()
    if draft is None:
        draft = SparkDraft(
            user_id=user_id,
            question_id=question_id,
            content="",
            expires_at=get_expiry_for_today(),
        )
        db.add(draft)
        await db.flush()
    return draft


async def has_submitted(
    db: AsyncSession,
    user_id: uuid.UUID,
    question_id: uuid.UUID,
) -> bool:
    result = await db.execute(
        select(SparkSubmission).where(
            SparkSubmission.user_id == user_id,
            SparkSubmission.question_id == question_id,
        )
    )
    return result.scalar_one_or_none() is not None
