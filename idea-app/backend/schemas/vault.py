"""仓库相关 schemas"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

BorderStyle = Literal["gold-thin", "none"]
VaultStatus = Literal["active", "fading", "faded"]


class VaultStats(BaseModel):
    """仓库统计"""
    produced: int = Field(0, ge=0, description="自己产生的点子数（金边）")
    collected: int = Field(0, ge=0, description="收集的点子数（无边）")
    forked_by_others: int = Field(
        0, ge=0, description="被别人 fork 的总数"
    )


class VaultCircle(BaseModel):
    """仓库圆圈"""
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="点子ID")
    color_hex: str = Field(
        ..., pattern=r"^#[0-9A-Fa-f]{6}$", description="圆圈颜色，#RRGGBB 格式"
    )
    size_score: float = Field(
        ..., ge=0, le=1, description="圆圈大小评分，0-1 之间"
    )
    border_style: BorderStyle = Field(
        ..., description="边框样式：gold-thin（自己产生）/ none（收集的）"
    )
    status: VaultStatus = Field(
        ..., description="点子状态：active（活跃）/ fading（淡出中）/ faded（已淡出）"
    )
    last_touch_at: datetime = Field(
        ..., description="最后被触碰时间（查看 / fork / 碰撞 / 演化）"
    )


class VaultResponse(BaseModel):
    """仓库列表响应"""
    stats: VaultStats = Field(..., description="仓库统计")
    circles: list[VaultCircle] = Field(
        default_factory=list, description="仓库圆圈列表"
    )
    has_more: bool = Field(False, description="是否还有更多数据")


class CollectResponse(BaseModel):
    """收集点子响应"""
    collected: bool = Field(True, description="是否收集成功")
    idea_id: str = Field(..., description="点子ID")


class RemoveResponse(BaseModel):
    """移出仓库响应"""
    removed: bool = Field(True, description="是否移出成功")
    idea_id: str = Field(..., description="点子ID")
