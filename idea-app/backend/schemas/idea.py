"""点子相关 schemas"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# 复用的 Literal 类型别名
IdeaSource = Literal["ugc", "pgc", "today_spark", "fork", "merge", "evolve"]
BorderStyle = Literal["gold-thin", "none"]
EvolveAngle = Literal[
    "substitute", "adapt", "modify", "put_to_other_use", "eliminate", "reverse"
]


class IdeaCreate(BaseModel):
    """发布新点子请求"""
    content: str = Field(
        ..., min_length=1, max_length=300, description="点子内容，1-300字"
    )


class IdeaForkRequest(BaseModel):
    """Fork 点子请求"""
    parent_id: str = Field(..., description="被 fork 的原点子ID")
    content: str = Field(
        ..., min_length=1, max_length=300, description="用户的联想内容，1-300字"
    )


class CircleData(BaseModel):
    """圆圈渲染数据（explore / vault 列表用）"""
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="点子ID")
    color_hex: str = Field(
        ...,
        pattern=r"^#[0-9A-Fa-f]{6}$",
        description="圆圈颜色，#RRGGBB 格式",
    )
    size_score: float = Field(
        ..., ge=0, le=1, description="圆圈大小评分，0-1 之间"
    )
    is_own: bool = Field(False, description="是否为自己产生的")
    fork_count: int = Field(0, ge=0, description="被 fork 数（用于大小计算）")
    border_style: BorderStyle | None = Field(
        None, description="边框样式：'gold-thin' 表示自己产生的金边，None 表示无边框"
    )


class ExploreResponse(BaseModel):
    """探索页响应"""
    circles: list[CircleData] = Field(
        default_factory=list, description="圆圈列表（不含点子内容）"
    )
    has_more: bool = Field(False, description="是否还有更多数据")


class LineageNode(BaseModel):
    """谱系图节点"""
    model_config = ConfigDict(from_attributes=True)

    # For a withdrawn/private source, id is an opaque lineage key, not the private Idea ID.
    id: str = Field(..., description="可访问节点为 Idea ID；不可访问的历史来源为不透明谱系键")
    color_hex: str = Field(
        ..., pattern=r"^#[0-9A-Fa-f]{6}$", description="圆圈颜色"
    )
    author: str = Field(..., description="创作时冻结的作者署名")
    title: str = Field(
        ..., max_length=30, description="点子标题；不可访问来源仅显示撤回占位文案"
    )
    is_navigable: bool = Field(True, description="是否允许打开该 Idea 详情")
    relation_type: Literal["fork", "merge", "evolve"] | None = None
    license_snapshot: dict | None = None


class Lineage(BaseModel):
    """谱系图（2层：父 + 子）"""
    parents: list[LineageNode] = Field(
        default_factory=list, description="父节点列表（0-2个）"
    )
    children: list[LineageNode] = Field(
        default_factory=list, description="子节点列表（最多10个）"
    )


class IdeaDetail(BaseModel):
    """点子详情"""
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="点子ID")
    content: str = Field(..., max_length=300, description="点子内容")
    color_hex: str = Field(
        ..., pattern=r"^#[0-9A-Fa-f]{6}$", description="圆圈颜色"
    )
    source: IdeaSource = Field(..., description="点子来源")
    author: dict = Field(
        ..., description="作者信息 {id, username, bio}"
    )
    created_at: datetime = Field(..., description="创建时间")
    fork_count: int = Field(0, ge=0, description="被 fork 数")
    is_forkable: bool = Field(True, description="当前用户是否可从该创意衍生")
    publication_status: Literal["draft", "published", "archived"] = "draft"
    visibility: Literal["private", "public"] = "private"
    license_code: str | None = None
    license_version: str | None = None
    access_role: Literal["owner", "contributor", "viewer"] | None = None
    is_in_vault: bool = Field(False, description="当前用户是否已收集")
    lineage: Lineage = Field(..., description="谱系图")


class IdeaResponse(BaseModel):
    """发布新点子响应"""
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="点子ID")
    content: str = Field(..., max_length=300, description="点子内容")
    color_hex: str = Field(
        ..., pattern=r"^#[0-9A-Fa-f]{6}$", description="圆圈颜色"
    )
    source: IdeaSource = Field(..., description="点子来源")
    author_id: str = Field(..., description="作者ID")
    created_at: datetime = Field(..., description="创建时间")
    border_style: BorderStyle = Field(
        ..., description="边框样式：gold-thin（自己产生）/ none（收集的）"
    )
    publication_status: Literal["draft", "published", "archived"] = "draft"
    visibility: Literal["private", "public"] = "private"
    license_code: str | None = None
    allow_fork: bool = False


class ForkResponse(BaseModel):
    """Fork 点子响应"""
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="新点子ID")
    parent_id: str = Field(..., description="原点子ID")
    content: str = Field(..., max_length=300, description="点子内容")
    color_hex: str = Field(
        ..., pattern=r"^#[0-9A-Fa-f]{6}$", description="圆圈颜色"
    )
    source: IdeaSource = Field(..., description="点子来源")
    border_style: BorderStyle = Field(
        ..., description="边框样式：gold-thin（自己产生）/ none（收集的）"
    )


class CollideRequest(BaseModel):
    """碰撞请求"""
    idea_a_id: str = Field(..., description="点子A的ID")
    idea_b_id: str = Field(..., description="点子B的ID")


class CollideSuggestion(BaseModel):
    """碰撞方案"""
    content: str = Field(..., max_length=300, description="方案内容，≤300字")
    type: Literal["practical", "cross_domain", "unconventional"] = Field(
        ...,
        description="方案类型：practical（实用型）/ cross_domain（跨界型）/ unconventional（反常规型）",
    )


class CollideResponse(BaseModel):
    """碰撞响应"""
    suggestions: list[CollideSuggestion] = Field(
        default_factory=list, description="3个碰撞方案"
    )
    # M4: AI 生成内容预览未审核，提示用户最终入库时会再次审核
    notice: str = Field(
        "AI 生成内容仅供预览，确认入库时将再次审核",
        description="风险提示",
    )


class CollideConfirmRequest(BaseModel):
    """碰撞确认请求"""
    idea_a_id: str = Field(..., description="点子A的ID")
    idea_b_id: str = Field(..., description="点子B的ID")
    content: str = Field(
        ..., min_length=1, max_length=300, description="用户选定的方案（可编辑），1-300字"
    )
    ai_assisted: bool = Field(..., description="是否 AI 辅助生成")


class CollideConfirmResponse(BaseModel):
    """碰撞确认响应"""
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="新点子ID")
    parent_ids: list[str] = Field(
        default_factory=list, description="父点子ID列表（2个）"
    )
    source: Literal["merge"] = Field(
        "merge", description="来源，固定为 merge"
    )
    border_style: BorderStyle = Field(
        ..., description="边框样式：gold-thin（自己产生）/ none（收集的）"
    )


class EvolveRequest(BaseModel):
    """演化请求"""
    idea_id: str = Field(..., description="点子ID")
    angle: EvolveAngle = Field(
        ...,
        description="SAMPER 演化角度：substitute / adapt / modify / put_to_other_use / eliminate / reverse",
    )


class EvolveVariant(BaseModel):
    """演化变体"""
    content: str = Field(..., max_length=300, description="变体内容，≤300字")
    distance: Literal["near", "medium", "bold"] = Field(
        ...,
        description="远离原点子的程度：near（微调）/ medium（明显变形）/ bold（大胆重构）",
    )


class EvolveResponse(BaseModel):
    """演化响应"""
    variants: list[EvolveVariant] = Field(
        default_factory=list, description="3个演化变体"
    )
    # M4: AI 生成内容预览未审核，提示用户最终入库时会再次审核
    notice: str = Field(
        "AI 生成内容仅供预览，确认入库时将再次审核",
        description="风险提示",
    )


class EvolveConfirmRequest(BaseModel):
    """演化确认请求"""
    parent_id: str = Field(..., description="父点子ID")
    angle: EvolveAngle = Field(
        ...,
        description="SAMPER 演化角度：substitute / adapt / modify / put_to_other_use / eliminate / reverse",
    )
    content: str = Field(
        ..., min_length=1, max_length=300, description="用户选定的变体，1-300字"
    )
    ai_assisted: bool = Field(..., description="是否 AI 辅助生成")


class EvolveConfirmResponse(BaseModel):
    """演化确认响应"""
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="新点子ID")
    parent_id: str = Field(..., description="父点子ID")
    evolved_from: str = Field(..., description="演化角度")
    source: Literal["evolve"] = Field(
        "evolve", description="来源，固定为 evolve"
    )
    border_style: BorderStyle = Field(
        ..., description="边框样式：gold-thin（自己产生）/ none（收集的）"
    )



class IdeaPublishRequest(BaseModel):
    """Explicit author confirmation required before public publication."""
    visibility: Literal["public", "private"] = "public"
    license_code: Literal[
        "all_rights_reserved", "attribution", "attribution_adaptation", "custom"
    ]
    license_custom_text: str | None = Field(None, max_length=5000)
    license_version: str = Field("v1", min_length=1, max_length=32)
    allow_fork: bool = False
    confirm_terms: bool = True


class IdeaInviteRequest(BaseModel):
    user_id: str = Field(..., description="被邀请用户 UUID")
    role: Literal["contributor", "viewer"] = "viewer"



class IdeaContributionCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=3000)
    note: str | None = Field(None, max_length=1000)


class IdeaContributionUpdate(BaseModel):
    content: str = Field(..., min_length=1, max_length=3000)
    note: str | None = Field(None, max_length=1000)


class IdeaContributionReview(BaseModel):
    decision: Literal["accepted", "rejected"]
    review_note: str | None = Field(None, max_length=1000)
