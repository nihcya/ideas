"""应用配置 - 通过环境变量加载"""
import re
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # 数据库
    # L3: 默认值仅 dev 用（dianzi_dev_pwd 占位密码），prod 必须通过 DATABASE_URL env 注入强密码
    database_url: str = "postgresql+asyncpg://dianzi:dianzi_dev_pwd@localhost:5432/dianzi_app"
    database_url_fallback: str = "sqlite+aiosqlite:///./dianzi_dev.db"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # DeepSeek
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"

    # JWT
    jwt_secret: str = ""  # 必须通过环境变量 JWT_SECRET 设置
    jwt_algorithm: str = "HS256"
    jwt_expire_days: int = 7

    # 用户 LLM API Key 加密密钥（Fernet），必须通过环境变量 LLM_KEY_ENCRYPTION_KEY 设置
    llm_key_encryption_key: str = ""

    # 应用
    app_env: str = "dev"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    # Comma-separated UUID allowlist for moderation/admin endpoints.
    admin_user_ids: str = ""
    # CORS:支持通配符 * 匹配任意端口(经 cors_origin_regex 转换为正则)。
    # dev: http://localhost:*,http://127.0.0.1:*
    # prod: https://example.com,https://app.example.com (精确域名,无通配符)
    cors_origins: str = "http://localhost:*,http://127.0.0.1:*"

    # 业务参数
    spark_duration_seconds: int = 180
    fade_fading_days: int = 7
    fade_faded_days: int = 8
    idea_max_length: int = 300
    # Historical public Ideas receive a 90-day license confirmation window after V2 activation.
    legacy_license_review_period_days: int = 90
    legacy_license_review_started_at: datetime | None = None

    @property
    def legacy_license_review_deadline_at(self) -> datetime | None:
        if self.legacy_license_review_started_at is None:
            return None
        started = self.legacy_license_review_started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        return started + timedelta(days=self.legacy_license_review_period_days)

    @property
    def is_deepseek_configured(self) -> bool:
        return bool(self.deepseek_api_key and self.deepseek_api_key.strip())

    @property
    def cors_origin_list(self) -> list[str]:
        """精确 origin 列表(无通配符时使用)。"""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def cors_origin_regex(self) -> str | None:
        """当 origins 含通配符 * 时,返回对应的正则;否则返回 None(用列表)。

        Starlette CORSMiddleware.allow_origins 不支持通配符,
        需用 allow_origin_regex 匹配 http://localhost:任意端口。
        """
        origins = self.cors_origin_list
        if not any("*" in o for o in origins):
            return None
        patterns = []
        for o in origins:
            # 转义特殊字符,然后把 \* 替换为 \d+(匹配任意端口)
            p = re.escape(o).replace(r"\*", r"\d+")
            patterns.append(p)
        return "|".join(patterns)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
