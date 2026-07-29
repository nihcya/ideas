"""内容审核服务 — 先发后审"""
from datetime import datetime, timezone
from typing import Optional
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import BannedWord, AuditLog, Idea
from services.deepseek_client import call_audit_ai


async def contains_banned_word(db: AsyncSession, content: str) -> tuple[bool, Optional[str]]:
    """违禁词精确匹配。"""
    result = await db.execute(select(BannedWord.word))
    banned = {row[0] for row in result.all()}
    for word in banned:
        if word in content:
            return True, word
    return False, None


async def audit_content(
    db: AsyncSession,
    content: str,
) -> tuple[bool, str]:
    """审核内容：先违禁词匹配，再AI语义审核。返回 (pass, reason)。

    审核统一使用全局 LLM 配置，不接受用户自定义 API 配置，
    防止用户通过自定义 endpoint 绕过审核。
    """
    # 1. 违禁词精确匹配
    hit, word = await contains_banned_word(db, content)
    if hit:
        return False, f"包含违禁词：{word}"

    # 2. AI 语义审核（fail-closed：审核服务不可用时拒绝入库，防止违规内容放行）
    try:
        result = await call_audit_ai(content)
        passed = bool(result.get("pass", True))
        reason = result.get("reason", "")
        return passed, reason
    except Exception:
        import logging
        logging.exception("AI audit service unavailable")
        return False, "审核服务暂时不可用，请稍后再试"


async def write_audit_log(
    db: AsyncSession,
    idea_id: Optional[uuid.UUID],
    content: str,
    passed: bool,
    reason: str,
    auditor: str = "ai",
) -> None:
    """写审核日志。"""
    log = AuditLog(
        idea_id=idea_id,
        content_snapshot=content,
        result="pass" if passed else "reject",
        reason=reason,
        auditor=auditor,
    )
    db.add(log)


async def reject_idea(db: AsyncSession, idea_id: uuid.UUID) -> None:
    """标记点子为已拒绝（违规撤回）。"""
    result = await db.execute(select(Idea).where(Idea.id == idea_id))
    idea = result.scalar_one_or_none()
    if idea:
        idea.status = "rejected"
        await db.flush()
