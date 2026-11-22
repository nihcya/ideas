"""PostgreSQL-only concurrency tests for version draft row locking.

This suite uses an isolated PostgreSQL database. SQLite is deliberately not used:
SQLite does not implement SELECT FOR UPDATE row-lock semantics.
"""
import asyncio
import os
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from models import Base, User, Idea, IdeaVersion
from routers import idea_versions as versions_router
from routers.idea_versions import VersionDraftCreate


@pytest.mark.asyncio
async def test_concurrent_draft_creation_serializes_on_idea_row(monkeypatch):
    dsn = os.getenv("IDEAS_VERSION_CONCURRENCY_TEST_DSN")
    if not dsn:
        pytest.skip("IDEAS_VERSION_CONCURRENCY_TEST_DSN is not configured")
    if dsn.startswith("postgresql://"):
        dsn = dsn.replace("postgresql://", "postgresql+asyncpg://", 1)

    async def allow_audit(*args, **kwargs):
        return True, ""

    async def noop_audit_log(*args, **kwargs):
        return None

    monkeypatch.setattr(versions_router, "audit_content", allow_audit)
    monkeypatch.setattr(versions_router, "write_audit_log", noop_audit_log)

    engine = create_async_engine(dsn, pool_size=5, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        # The CI job owns a disposable database; no production DSN is used.
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

        owner_id = uuid.uuid4()
        idea_id = uuid.uuid4()
        async with sessions() as seed:
            seed.add(User(
                id=owner_id,
                username=f"pg_concurrency_{uuid.uuid4().hex[:10]}",
                password_hash="test-only",
            ))
            seed.add(Idea(
                id=idea_id,
                content="并发版本草稿测试",
                color_hex="#123456",
                source="ugc",
                author_id=owner_id,
                border_style="gold-thin",
                publication_status="draft",
                visibility="private",
                status="active",
            ))
            await seed.commit()

        async def create_draft(content: str):
            async with sessions() as session:
                owner = await session.get(User, owner_id)
                try:
                    result = await versions_router.create_version_draft(
                        idea_id,
                        VersionDraftCreate(content=content),
                        session,
                        owner,
                    )
                    return ("created", result["id"])
                except HTTPException as exc:
                    await session.rollback()
                    return ("http_error", exc.status_code)

        outcomes = await asyncio.gather(
            create_draft("并发请求 A 创建的版本"),
            create_draft("并发请求 B 创建的版本"),
        )
        assert sorted(item[0] for item in outcomes) == ["created", "http_error"]
        assert next(item[1] for item in outcomes if item[0] == "http_error") == 409

        async with sessions() as verify:
            count = await verify.scalar(
                select(func.count()).select_from(IdeaVersion).where(
                    IdeaVersion.idea_id == idea_id,
                    IdeaVersion.status == "draft",
                )
            )
            assert count == 1
            version_number = await verify.scalar(
                select(IdeaVersion.version_number).where(
                    IdeaVersion.idea_id == idea_id
                )
            )
            assert version_number == 1
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()
