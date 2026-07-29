from __future__ import annotations

from typing import Optional
import uuid

from sqlalchemy import String, Uuid, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class SecurityEvent(Base):
    """M8: 安全事件审计日志表

    记录登录失败、权限拒绝、SSRF 触发、token 撤销等安全相关事件，
    用于事后审计和告警。与 audit_logs（内容审核结果）区分。
    """

    __tablename__ = "security_events"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    # 事件类型：login_failed / login_success / logout / permission_denied /
    # ssrf_blocked / token_revoked / rate_limited / register_failed 等
    action: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    # 关联用户（可能为空，如登录失败时未知）
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, nullable=True, index=True
    )
    # 用户名（登录场景下记录，便于按用户名聚合）
    username: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # 客户端 IP
    ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # 结果：success / failure
    result: Mapped[str] = mapped_column(String(10), nullable=False)
    # 原因/详情（如「密码错误」「SSRF 拦截: 127.0.0.1」「token 已撤销」）
    reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # 创建时间（独立字段，不使用 TimestampMixin 的 created_at 避免依赖）
    ts: Mapped[Optional[str]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
