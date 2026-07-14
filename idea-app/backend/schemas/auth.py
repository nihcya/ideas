"""认证相关 schemas"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RegisterRequest(BaseModel):
    """注册请求"""
    username: str = Field(
        ...,
        min_length=3,
        max_length=20,
        pattern=r"^[a-zA-Z0-9_\u4e00-\u9fa5]+$",
        description="用户名，3-20字符，支持字母数字下划线及中文",
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="密码，至少8位",
    )
    bio: str = Field(
        "",
        max_length=50,
        description="一句话简介，0-50字符",
    )


class LoginRequest(BaseModel):
    """登录请求"""
    username: str = Field(..., min_length=1, max_length=20, description="用户名")
    password: str = Field(..., min_length=1, max_length=128, description="密码")


class AuthResponse(BaseModel):
    """认证响应（注册/登录通用）"""
    model_config = ConfigDict(from_attributes=True)

    user_id: str = Field(..., description="用户ID（UUID字符串）")
    username: str = Field(..., description="用户名")
    token: str = Field(..., description="JWT token")
