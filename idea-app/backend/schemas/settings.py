"""设置相关 schemas"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _mask_api_key(key: str) -> str:
    """脱敏 API key：前3后4，中间星号。空则返回空。"""
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return f"{key[:3]}{'*' * (len(key) - 7)}{key[-4:]}"


class SettingsResponse(BaseModel):
    """设置响应"""
    model_config = ConfigDict(from_attributes=True)

    dark_mode: bool = Field(False, description="是否暗色模式")
    forkable: bool = Field(True, description="是否允许他人 fork 我的点子")
    username: str = Field(..., description="用户名")
    bio: str = Field(..., max_length=50, description="一句话简介，0-50字符")
    # 大模型配置（脱敏回读）
    llm_api_url: str = Field("", description="大模型 API 地址（OpenAI 兼容）")
    llm_api_key: str = Field("", description="大模型 API 密钥（脱敏）")
    llm_api_key_configured: bool = Field(
        False, description="是否已配置 API 密钥（用于前端区分空与占位）"
    )


class SettingsUpdateRequest(BaseModel):
    """更新设置请求（所有字段可选）"""
    dark_mode: bool | None = Field(None, description="是否暗色模式")
    forkable: bool | None = Field(
        None, description="是否允许他人 fork 我的点子"
    )
    bio: str | None = Field(
        None, max_length=50, description="一句话简介，0-50字符"
    )
    # 大模型配置（明文写入，空字符串表示清除）
    llm_api_url: str | None = Field(
        None, max_length=255, description="大模型 API 地址"
    )
    llm_api_key: str | None = Field(
        None, max_length=255, description="大模型 API 密钥"
    )

    @field_validator("llm_api_url")
    @classmethod
    def validate_url(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return v
        v = v.strip()
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("API 地址必须以 http:// 或 https:// 开头")
        # SSRF 防护：拦截内网/元数据地址
        parsed = urlparse(v)
        host = parsed.hostname
        if not host:
            raise ValueError("URL 缺少主机名")
        # 拦截已知内网域名
        if host in ("localhost", "postgres", "redis", "db", "mysql"):
            raise ValueError("不允许的内网地址")
        # 判断 host 是否为 IP 格式：ipaddress.ip_address 对非 IP 字符串抛 ValueError
        # 注意：必须用 flag 区分，避免我们主动抛的 ValueError 被外层 except 吞掉
        is_ip = False
        try:
            ipaddress.ip_address(host)
            is_ip = True
        except ValueError:
            is_ip = False
        if is_ip:
            # host 是 IP 字面量：拦截私有/保留段
            ip = ipaddress.ip_address(host)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                raise ValueError("不允许的内网 IP 地址")
        else:
            # host 是域名：解析后校验解析结果
            try:
                resolved = socket.gethostbyname(host)
                ip = ipaddress.ip_address(resolved)
                if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                    raise ValueError(f"域名 {host} 解析到内网 IP，不允许")
            except socket.gaierror:
                # 域名解析失败，放行让 LLM 调用时报错
                pass
        return v
