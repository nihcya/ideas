"""M8: 安全事件审计服务

记录登录失败/成功、登出、权限拒绝、SSRF 拦截、token 撤销等安全事件。
写入失败不阻塞主流程（安全日志丢失不应影响业务）。
"""
from __future__ import annotations

import logging
import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from models import SecurityEvent

logger = logging.getLogger(__name__)


async def log_security_event(
    db: AsyncSession,
    action: str,
    result: str,
    *,
    user_id: Optional[uuid.UUID | str] = None,
    username: Optional[str] = None,
    ip: Optional[str] = None,
    reason: Optional[str] = None,
    commit: bool = False,
) -> None:
    """记录一条安全事件。

    Args:
        db: 数据库会话
        action: 事件类型，如 login_failed / logout / ssrf_blocked
        result: success / failure
        user_id: 关联用户 ID（可空）
        username: 用户名（可空）
        ip: 客户端 IP（可空）
        reason: 详情/原因（可空）
        commit: 是否立即提交（默认 False，由调用方统一提交）

    写入失败仅记录日志，不抛异常，避免影响主业务流程。
    """
    try:
        event = SecurityEvent(
            action=action,
            result=result,
            user_id=uuid.UUID(str(user_id)) if user_id else None,
            username=username,
            ip=ip,
            reason=reason,
        )
        db.add(event)
        if commit:
            await db.commit()
    except Exception:
        logger.exception("Failed to log security event: action=%s", action)
        # 回滚 add 操作避免污染会话
        try:
            await db.rollback()
        except Exception:
            pass
