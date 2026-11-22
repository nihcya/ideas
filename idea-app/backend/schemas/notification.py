"""通知相关 schemas"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

NotificationType = Literal["forked", "collected", "spark_updated", "collab_published", "collab_invited", "collab_reviewed", "legacy_license_reminder"]


class NotificationItem(BaseModel):
    """通知条目"""
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="通知ID")
    type: NotificationType = Field(
        ...,
        description="通知类型：forked（被fork）/ collected（被收集）/ spark_updated（今日一点更新）",
    )
    content: str = Field(..., max_length=200, description="通知文案")
    idea_id: str | None = Field(
        None, description="相关点子ID，无则为 None"
    )
    actor_id: str | None = Field(
        None, description="触发者用户ID，无则为 None"
    )
    collaboration_id: str | None = Field(
        None, description="关联协作空间 ID，用于通知深链"
    )
    created_at: datetime = Field(..., description="创建时间")
    read: bool = Field(False, description="是否已读")


class NotificationsResponse(BaseModel):
    """通知列表响应"""
    notifications: list[NotificationItem] = Field(
        default_factory=list, description="通知列表"
    )
    unread_count: int = Field(0, ge=0, description="未读通知数")


class MarkReadRequest(BaseModel):
    """标记已读请求"""
    notification_ids: list[str] = Field(
        ..., min_length=1, description="要标记已读的通知ID列表"
    )


class MarkReadResponse(BaseModel):
    """标记已读响应"""
    marked_read: int = Field(
        ..., ge=0, description="成功标记已读的通知数量"
    )
