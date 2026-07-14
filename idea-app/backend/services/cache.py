"""Redis 缓存 — 含同步兜底（Redis 不可用时退化为内存字典）。"""
import json
import time
import uuid
from typing import Any, Optional

try:
    import redis.asyncio as aioredis
    _HAS_REDIS = True
except ImportError:
    _HAS_REDIS = False

from config import settings


class InMemoryCache:
    """简易内存缓存，TTL 支持。"""

    def __init__(self) -> None:
        self._store: dict[str, tuple[Any, float]] = {}

    async def get(self, key: str) -> Optional[Any]:
        item = self._store.get(key)
        if item is None:
            return None
        value, expires_at = item
        if expires_at < time.time():
            self._store.pop(key, None)
            return None
        return value

    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        self._store[key] = (value, time.time() + ttl)

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def delete_pattern(self, pattern: str) -> None:
        # 简易实现：只支持 * 通配符
        import fnmatch
        keys_to_delete = [k for k in self._store.keys() if fnmatch.fnmatch(k, pattern)]
        for k in keys_to_delete:
            self._store.pop(k, None)


class CacheService:
    """Redis 优先，不可用时退化为内存。"""

    def __init__(self) -> None:
        self._redis = None
        self._fallback = InMemoryCache()
        self._use_redis = False

    async def init(self) -> None:
        if not _HAS_REDIS:
            print("[cache] redis package not installed, using in-memory fallback")
            return
        try:
            self._redis = aioredis.from_url(settings.redis_url, decode_responses=True)
            await self._redis.ping()
            self._use_redis = True
            print("[cache] Redis connected")
        except Exception as e:
            print(f"[cache] Redis unavailable, using in-memory fallback: {e}")
            self._redis = None
            self._use_redis = False

    async def close(self) -> None:
        if self._redis:
            await self._redis.close()

    async def get(self, key: str) -> Optional[Any]:
        if self._use_redis:
            raw = await self._redis.get(key)
            if raw is None:
                return None
            try:
                return json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                return raw
        return await self._fallback.get(key)

    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        if self._use_redis:
            await self._redis.set(key, json.dumps(value, default=str), ex=ttl)
        else:
            await self._fallback.set(key, value, ttl)

    async def delete(self, key: str) -> None:
        if self._use_redis:
            await self._redis.delete(key)
        else:
            await self._fallback.delete(key)

    async def delete_pattern(self, pattern: str) -> None:
        if self._use_redis:
            async for key in self._redis.scan_iter(match=pattern):
                await self._redis.delete(key)
        else:
            await self._fallback.delete_pattern(pattern)

    # ============================================================
    # 互斥锁：防止缓存击穿（cache stampede）
    # ============================================================
    # 用法：
    #   lock_token = await cache.acquire_lock("explore:lock:0", ttl=10)
    #   if lock_token:
    #       try:
    #           # 查库 + 写缓存
    #       finally:
    #           await cache.release_lock("explore:lock:0", lock_token)
    #   else:
    #       # 等几十毫秒重试读缓存
    # Redis 用 SET NX PX，内存模式用字典+TTL 模拟

    async def acquire_lock(self, key: str, ttl: int = 10) -> Optional[str]:
        """尝试获取互斥锁。成功返回 token（释放时用），失败返回 None。"""
        token = uuid.uuid4().hex
        if self._use_redis:
            # SET key value NX PX ttl —— 原子操作
            ok = await self._redis.set(key, token, nx=True, px=ttl * 1000)
            return token if ok else None
        # 内存模式：用 _store 模拟，TTL 短一些避免死锁
        now = time.time()
        existing = self._fallback._store.get(key)
        if existing and existing[1] > now:
            return None
        self._fallback._store[key] = (token, now + ttl)
        return token

    async def release_lock(self, key: str, token: str) -> None:
        """释放锁。只有 token 匹配才删（避免误删别人的锁）。"""
        if self._use_redis:
            # Lua 脚本保证原子：只有值匹配才删
            lua = (
                "if redis.call('get', KEYS[1]) == ARGV[1] "
                "then return redis.call('del', KEYS[1]) "
                "else return 0 end"
            )
            try:
                await self._redis.eval(lua, 1, key, token)
            except Exception:
                pass
            return
        # 内存模式
        existing = self._fallback._store.get(key)
        if existing and existing[0] == token:
            self._fallback._store.pop(key, None)

    async def wait_for_cache(self, key: str, retries: int = 5, interval: float = 0.05) -> Optional[Any]:
        """轮询等待其他 worker 写入缓存，最多 retries 次。"""
        for _ in range(retries):
            val = await self.get(key)
            if val is not None:
                return val
            await asyncio_sleep(interval)
        return None


# 全局单例
cache = CacheService()


async def asyncio_sleep(seconds: float) -> None:
    import asyncio
    await asyncio.sleep(seconds)


# ============================================================
# 缓存 Key 工具
# ============================================================

def key_explore_page(offset: int) -> str:
    return f"explore:page:{offset}"


def key_idea_detail(idea_id: str) -> str:
    return f"idea:detail:{idea_id}"


def key_user_vault(user_id: str) -> str:
    return f"user:vault:{user_id}"


def key_spark_today() -> str:
    return "spark:today"


def key_user_stats(user_id: str) -> str:
    return f"user:stats:{user_id}"


def key_notifications_unread(user_id: str) -> str:
    return f"notifications:unread:{user_id}"
