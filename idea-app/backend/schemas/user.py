"""用户主页相关 schemas"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class UserProfile(BaseModel):
    """用户公开主页（思维森林）"""
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="用户ID")
    username: str = Field(..., description="用户名")
    bio: str = Field(..., description="一句话简介")
    is_self: bool = Field(False, description="当前登录用户是否为主页所有者")
    is_following: bool = Field(False, description="当前登录用户是否已关注该创作者")
    can_follow: bool = Field(False, description="当前用户是否可以关注该创作者")
    stats: dict = Field(
        default_factory=dict,
        description="统计信息 {produced, collected, forked_by_others, forked_others}",
    )
    circles: list[dict] = Field(
        default_factory=list,
        description="仓库圆圈列表，每个元素 {id, color_hex, size_score, border_style}",
    )
