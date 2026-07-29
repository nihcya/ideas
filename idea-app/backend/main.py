"""FastAPI 主入口"""
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from config import settings
from database import init_engine, close_engine, DB_DIALECT
from services.cache import cache
from services.rate_limit import limiter
from routers import get_all_routers


# ============================================================
# 单 worker 执行锁：防止多 gunicorn worker 重复跑定时任务
# ============================================================
# 方案：
#   - PostgreSQL: pg_try_advisory_lock（推荐，无副作用）
#   - SQLite: 文件锁（fallback，单机单 worker 场景才用到）
#   - 通过环境变量 DIANZI_SCHEDULER_ENABLED=1 显式开启，
#     推荐生产只让 1 个 worker 启用，彻底避免竞态

SCHEDULER_LOCK_KEY = 0x_D1A2_3BEF  # 自定义 advisory lock key


def _scheduler_enabled() -> bool:
    """是否启用本进程的 scheduler。

    优先级：
      1. 环境变量 DIANZI_SCHEDULER_ENABLED=1/0 显式控制
      2. APP_ENV=prod 时默认关闭（推荐单 worker 通过 env 开启）
      3. dev / sqlite 模式默认开启
    """
    env_flag = os.environ.get("DIANZI_SCHEDULER_ENABLED", "").lower()
    if env_flag in ("1", "true", "yes"):
        return True
    if env_flag in ("0", "false", "no"):
        return False
    # 未显式指定：prod 默认关（让运维在 1 个 worker 上显式打开）
    if settings.app_env == "prod":
        return False
    return True


async def _try_acquire_pg_advisory_lock(session, key: int) -> bool:
    """PG 试图获取会话级 advisory lock。

    成功返回 True，已被其他 worker 占用返回 False。
    SQLite 会直接返回 True（SQLite 单写入者，不存在多 worker 问题）。
    """
    if not DB_DIALECT.startswith("postgresql"):
        return True
    from sqlalchemy import text
    result = await session.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": key})
    return bool(result.scalar())


async def _release_pg_advisory_lock(session, key: int) -> None:
    if not DB_DIALECT.startswith("postgresql"):
        return
    from sqlalchemy import text
    await session.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": key})


# ============================================================
# 定时任务（APScheduler）
# ============================================================

def _setup_scheduler() -> "AsyncIOScheduler":
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    from services.fade_service import check_and_fade

    scheduler = AsyncIOScheduler()

    @scheduler.scheduled_job(CronTrigger(hour=1, minute=0))
    async def _natural_fade_job():
        """每日 01:00 自然淡出检查

        多 worker 防重复：先抢 PG advisory lock，抢不到说明已有 worker 在跑。
        """
        import database
        session_cm = database.db_session()
        session = await session_cm.__aenter__()
        try:
            locked = await _try_acquire_pg_advisory_lock(session, SCHEDULER_LOCK_KEY)
            if not locked:
                print("[scheduler] fade job skipped: another worker holds the lock")
                return
            stats = await check_and_fade(session)
            print(f"[scheduler] fade job done: {stats}")
        except Exception as e:
            print(f"[scheduler] fade job failed: {e}")
        finally:
            await _release_pg_advisory_lock(session, SCHEDULER_LOCK_KEY)
            await session_cm.__aexit__(None, None, None)

    @scheduler.scheduled_job(CronTrigger(hour=0, minute=0))
    async def _cleanup_drafts_job():
        """每日 00:00 清理过期草稿（同样用 advisory lock 防重复）"""
        from sqlalchemy import delete
        from models import SparkDraft
        import database
        session_cm = database.db_session()
        session = await session_cm.__aenter__()
        try:
            locked = await _try_acquire_pg_advisory_lock(session, SCHEDULER_LOCK_KEY)
            if not locked:
                print("[scheduler] cleanup drafts skipped: another worker holds the lock")
                return
            now = datetime.now(timezone.utc)
            result = await session.execute(
                delete(SparkDraft).where(SparkDraft.expires_at < now)
            )
            await session.commit()
            print(f"[scheduler] cleanup drafts: {result.rowcount}")
        except Exception as e:
            print(f"[scheduler] cleanup drafts failed: {e}")
        finally:
            await _release_pg_advisory_lock(session, SCHEDULER_LOCK_KEY)
            await session_cm.__aexit__(None, None, None)

    @scheduler.scheduled_job(CronTrigger(hour=0, minute=5))
    async def _spark_question_job():
        """每日 00:05 预生成当日「今日一点」题目

        多 worker 防重复：
        1. Advisory Lock 抢锁，抢不到说明已有 worker 在跑
        2. generate_and_persist 内部有二次 SELECT 检查 + date 唯一约束兜底
        """
        from datetime import date as date_type
        from services.spark_ai_service import generate_and_persist
        import database
        session_cm = database.db_session()
        session = await session_cm.__aenter__()
        try:
            locked = await _try_acquire_pg_advisory_lock(session, SCHEDULER_LOCK_KEY)
            if not locked:
                print("[scheduler] spark question skipped: another worker holds the lock")
                return
            today = date_type.today()
            q = await generate_and_persist(session, today)
            if q is not None:
                print(f"[scheduler] spark question generated: date={q.date} type={q.type} q={q.question[:30]}...")
            else:
                print(f"[scheduler] spark question generation returned None for {today}")
        except Exception as e:
            print(f"[scheduler] spark question failed: {e}")
        finally:
            await _release_pg_advisory_lock(session, SCHEDULER_LOCK_KEY)
            await session_cm.__aexit__(None, None, None)

    return scheduler


# ============================================================
# 应用生命周期
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动
    # JWT 密钥校验
    if not settings.jwt_secret:
        if settings.app_env == "prod":
            raise RuntimeError("[FATAL] JWT_SECRET 环境变量未设置，生产环境拒绝启动")
        else:
            import secrets as _secrets
            settings.jwt_secret = _secrets.token_urlsafe(32)
            print("[WARN] JWT_SECRET 未设置，dev 模式生成临时密钥")
    # API Key 加密密钥校验
    if settings.app_env == "prod" and not settings.llm_key_encryption_key:
        raise RuntimeError("[FATAL] LLM_KEY_ENCRYPTION_KEY 未设置，生产环境拒绝启动")

    print("[startup] initializing database...")
    await init_engine()
    print("[startup] initializing cache...")
    await cache.init()

    print("[startup] starting scheduler...")
    if _scheduler_enabled():
        scheduler = _setup_scheduler()
        scheduler.start()
        app.state.scheduler = scheduler
        print(f"[startup] scheduler enabled (env={settings.app_env})")
    else:
        # prod 模式默认不启动，由 DIANZI_SCHEDULER_ENABLED=1 显式开启
        # 推荐用 gunicorn --env DIANZI_SCHEDULER_ENABLED=1 让单 worker 启动
        print(f"[startup] scheduler disabled (env={settings.app_env}, set DIANZI_SCHEDULER_ENABLED=1 to enable)")

    print("[startup] ready")
    yield

    # 关闭
    print("[shutdown] stopping scheduler...")
    if hasattr(app.state, "scheduler"):
        app.state.scheduler.shutdown(wait=False)
    print("[shutdown] closing cache...")
    await cache.close()
    print("[shutdown] closing database...")
    await close_engine()
    print("[shutdown] done")


# ============================================================
# FastAPI 应用
# ============================================================

app = FastAPI(
    title="点子 App API",
    description="创意激发社区 — Flutter + FastAPI + DeepSeek",
    version="0.1.0",
    lifespan=lifespan,
)

# 速率限制
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"error": {"code": "RATE_LIMITED", "message": "请求过于频繁，请稍后再试"}},
    )

# CORS:dev 模式用 regex 匹配 localhost:任意端口,prod 用精确列表
# Starlette CORSMiddleware.allow_origins 不支持通配符,
# 需用 allow_origin_regex 才能匹配 http://localhost:52990 这样的动态端口
# H3 收敛:methods/headers 仅允许实际使用的方法和头,避免过度暴露
if settings.cors_origin_regex:
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=settings.cors_origin_regex,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
        allow_headers=["Authorization", "Content-Type"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
        allow_headers=["Authorization", "Content-Type"],
    )


# 统一错误格式
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """非 HTTPException 的异常统一返回 500。"""
    import traceback
    print(f"[error] unhandled: {exc}\n{traceback.format_exc()}")
    # 生产环境不泄露内部错误细节
    safe_message = "服务器内部错误" if settings.app_env == "prod" else str(exc)
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "INTERNAL_ERROR", "message": safe_message}},
    )


# 注册所有路由
for router in get_all_routers():
    app.include_router(router, prefix="/api")


# 健康检查
@app.get("/health")
async def health():
    return {"status": "ok", "env": settings.app_env, "ts": datetime.now(timezone.utc).isoformat()}


@app.get("/")
async def root():
    return {
        "name": "点子 App API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_env == "dev",
    )
