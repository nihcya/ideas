"""pytest 配置：使用 SQLite 内存库做隔离测试。

并发测试不依赖真实 PG/Redis，用 SQLite + asyncio 协程并发模拟竞态。
"""
import asyncio
import os
import sys
from pathlib import Path

# 把 backend 加入 sys.path，方便 import
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# 强制使用 SQLite 内存库 + 关闭 scheduler
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///file::memory:?cache=shared&uri=true"
os.environ["DATABASE_URL_FALLBACK"] = "sqlite+aiosqlite:///file::memory:?cache=shared&uri=true"
os.environ["APP_ENV"] = "test"
os.environ["DIANZI_SCHEDULER_ENABLED"] = "0"

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from models import Base


@pytest_asyncio.fixture
async def memory_engine():
    """每个测试函数独立的内存 SQLite 引擎，互不污染。"""
    # 每次创建新文件，避免跨测试数据污染
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(memory_engine):
    """独立 session，测试完回滚。"""
    factory = async_sessionmaker(memory_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()
