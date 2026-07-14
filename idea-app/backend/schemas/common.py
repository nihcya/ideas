"""通用响应 schemas"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ErrorDetail(BaseModel):
    """错误详情"""
    code: str = Field(..., description="错误代码，如 NOT_FOUND、UNAUTHORIZED")
    message: str = Field(..., description="人类可读的错误描述")


class ErrorResponse(BaseModel):
    """统一错误响应"""
    error: ErrorDetail = Field(..., description="错误详情对象")


class PaginatedMeta(BaseModel):
    """分页元信息"""
    has_more: bool = Field(False, description="是否还有更多数据")


class SuccessResponse(BaseModel):
    """通用成功响应"""
    model_config = ConfigDict(from_attributes=True)

    success: bool = Field(True, description="操作是否成功")
    message: str | None = Field(None, description="可选的成功提示消息")
