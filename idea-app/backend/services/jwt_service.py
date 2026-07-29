"""JWT 服务 — 签发 + 验证 + 撤销（黑名单）"""
from datetime import datetime, timedelta, timezone
from typing import Optional
import uuid

from jose import JWTError, jwt

from config import settings


# 黑名单 cache key 前缀：revoked token 按 jti 索引
_REVOKED_KEY_PREFIX = "jwt:revoked:"


def _revoked_key(jti: str) -> str:
    return f"{_REVOKED_KEY_PREFIX}{jti}"


def create_access_token(user_id: str | uuid.UUID, username: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "username": username,
        "iat": now,
        "exp": now + timedelta(days=settings.jwt_expire_days),
        "jti": uuid.uuid4().hex,  # 唯一 ID，用于撤销
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None


async def revoke_token(token: str) -> bool:
    """将 token 加入黑名单（用于登出）。TTL = token 剩余有效期。

    返回 True 表示撤销成功，False 表示 token 无效或已过期。
    """
    payload = decode_token(token)
    if payload is None:
        return False
    jti = payload.get("jti")
    exp = payload.get("exp")
    if not jti or not exp:
        return False
    # 计算剩余有效期（秒），至少 1 秒
    now = datetime.now(timezone.utc).timestamp()
    remaining = max(1, int(exp) - int(now))
    # 延迟导入避免循环依赖
    from services.cache import cache
    await cache.set(_revoked_key(jti), "1", ttl=remaining)
    return True


async def is_token_revoked(payload: dict) -> bool:
    """检查 token 是否已被撤销。"""
    jti = payload.get("jti")
    if not jti:
        # 旧 token 无 jti，不拦截（向后兼容）
        return False
    from services.cache import cache
    val = await cache.get(_revoked_key(jti))
    return val is not None
