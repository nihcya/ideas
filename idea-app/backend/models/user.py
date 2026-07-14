from __future__ import annotations

from sqlalchemy import String, Boolean, DateTime, func, Uuid
from sqlalchemy.orm import Mapped, mapped_column
import uuid

from .base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    bio: Mapped[str] = mapped_column(String(50), default="", server_default="")
    dark_mode: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    forkable: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    # 用户自定义大模型配置（OpenAI 兼容协议）
    # 留空时回退到后端全局 .env 配置；都为空时走 Mock
    llm_api_url: Mapped[str] = mapped_column(String(255), default="", server_default="")
    llm_api_key: Mapped[str] = mapped_column(String(255), default="", server_default="")
