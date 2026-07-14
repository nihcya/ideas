"""今日一点相关 schemas"""
from datetime import date as date_type, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SparkType = Literal["random_word", "analogy", "constraint", "reverse_question"]


class SparkTodayResponse(BaseModel):
    """今日一点题目响应"""
    model_config = ConfigDict(from_attributes=True)

    date: date_type = Field(..., description="题目日期，如 2026-07-08")
    question: str = Field(..., description="题目内容")
    type: SparkType = Field(
        ...,
        description="题目类型：random_word / analogy / constraint / reverse_question",
    )
    duration_seconds: int = Field(
        180, ge=0, description="建议作答时长（秒）"
    )
    has_draft: bool = Field(False, description="是否已有草稿")
    submitted: bool = Field(False, description="是否已提交")


class SparkDraftRequest(BaseModel):
    """保存草稿请求"""
    content: str = Field(
        ..., min_length=1, max_length=300, description="草稿内容，1-300字"
    )


class SparkDraftResponse(BaseModel):
    """保存草稿响应"""
    saved: bool = Field(True, description="是否保存成功")
    expires_at: datetime = Field(
        ..., description="草稿过期时间（当日 23:59:59）"
    )
    first_save: bool = Field(
        False, description="是否首次保存（前端弹窗提示用）"
    )


class SparkSubmitRequest(BaseModel):
    """提交今日一点请求"""
    content: str = Field(
        ..., min_length=1, max_length=300, description="提交内容，1-300字"
    )


class SparkSubmitResponse(BaseModel):
    """提交今日一点响应"""
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="新点子ID")
    source: Literal["today_spark"] = Field(
        "today_spark", description="来源，固定为 today_spark"
    )
    border_style: Literal["gold-thin"] = Field(
        "gold-thin", description="边框样式，固定为 gold-thin"
    )
    color_hex: str = Field(
        ..., pattern=r"^#[0-9A-Fa-f]{6}$", description="圆圈颜色，#RRGGBB 格式"
    )
