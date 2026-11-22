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

from models import Base, User, Idea, IdeaVersion, IdeaContribution, IdeaVersionContribution
from routers import idea_versions as versions_router
from routers.idea_versions import VersionDraftCreate, VersionDraftUpdate


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
                username=f"pgc_{uuid.uuid4().hex[:10]}",
                password_hash="test-only",
            ))
            # Flush the referenced row explicitly before inserting the Idea.
            await seed.flush()
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



@pytest.mark.asyncio
async def test_concurrent_draft_updates_cannot_claim_same_contribution(monkeypatch):
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
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

        owner_id, idea_id, contribution_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        version_ids = [uuid.uuid4(), uuid.uuid4()]
        async with sessions() as seed:
            seed.add(User(
                id=owner_id,
                username=f"pgc_{uuid.uuid4().hex[:10]}",
                password_hash="test-only",
            ))
            await seed.flush()
            seed.add(Idea(
                id=idea_id,
                content="并发贡献归属测试",
                color_hex="#123456",
                source="ugc",
                author_id=owner_id,
                border_style="gold-thin",
                publication_status="draft",
                visibility="private",
                status="active",
            ))
            await seed.flush()
            seed.add(IdeaContribution(
                id=contribution_id,
                idea_id=idea_id,
                author_id=owner_id,
                content="被两个草稿同时选择的贡献",
                status="accepted",
            ))
            for number, version_id in enumerate(version_ids, start=1):
                seed.add(IdeaVersion(
                    id=version_id,
                    idea_id=idea_id,
                    version_number=number,
                    content_snapshot=f"旧草稿内容 {number}",
                    status="draft",
                    created_by=owner_id,
                ))
            await seed.commit()

        async def attach(version_id, content):
            async with sessions() as session:
                owner = await session.get(User, owner_id)
                try:
                    result = await versions_router.update_version_draft(
                        idea_id,
                        version_id,
                        VersionDraftUpdate(
                            content=content,
                            contribution_ids=[contribution_id],
                        ),
                        session,
                        owner,
                    )
                    return ("updated", result["id"])
                except HTTPException as exc:
                    await session.rollback()
                    return ("http_error", exc.status_code)

        outcomes = await asyncio.gather(
            attach(version_ids[0], "草稿 A"),
            attach(version_ids[1], "草稿 B"),
        )
        assert sorted(item[0] for item in outcomes) == ["http_error", "updated"]
        assert next(item[1] for item in outcomes if item[0] == "http_error") == 409

        async with sessions() as verify:
            count = await verify.scalar(
                select(func.count()).select_from(IdeaVersionContribution).where(
                    IdeaVersionContribution.contribution_id == contribution_id
                )
            )
            assert count == 1
            mapping = await verify.scalar(
                select(IdeaVersionContribution.version_id).where(
                    IdeaVersionContribution.contribution_id == contribution_id
                )
            )
            assert mapping in version_ids
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()



@pytest.mark.asyncio
async def test_concurrent_publish_requests_publish_version_once(monkeypatch):
    dsn = os.getenv("IDEAS_VERSION_CONCURRENCY_TEST_DSN")
    if not dsn:
        pytest.skip("IDEAS_VERSION_CONCURRENCY_TEST_DSN is not configured")
    if dsn.startswith("postgresql://"):
        dsn = dsn.replace("postgresql://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(dsn, pool_size=5, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

        owner_id, idea_id, version_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        async with sessions() as seed:
            seed.add(User(
                id=owner_id,
                username=f"pgc_{uuid.uuid4().hex[:10]}",
                password_hash="test-only",
            ))
            await seed.flush()
            seed.add(Idea(
                id=idea_id,
                content="发布前的创意内容",
                color_hex="#123456",
                source="ugc",
                author_id=owner_id,
                border_style="gold-thin",
                publication_status="draft",
                visibility="private",
                status="active",
            ))
            await seed.flush()
            seed.add(IdeaVersion(
                id=version_id,
                idea_id=idea_id,
                version_number=1,
                content_snapshot="并发发布的目标版本",
                status="draft",
                created_by=owner_id,
            ))
            await seed.commit()

        async def publish():
            async with sessions() as session:
                owner = await session.get(User, owner_id)
                try:
                    result = await versions_router.publish_version(
                        idea_id, version_id, session, owner
                    )
                    return ("published", result["published"])
                except HTTPException as exc:
                    await session.rollback()
                    return ("http_error", exc.status_code)

        outcomes = await asyncio.gather(publish(), publish())
        assert sorted(item[0] for item in outcomes) == ["http_error", "published"]
        assert next(item[1] for item in outcomes if item[0] == "http_error") == 404

        async with sessions() as verify:
            version = await verify.get(IdeaVersion, version_id)
            idea = await verify.get(Idea, idea_id)
            assert version.status == "published"
            assert version.published_at is not None
            assert idea.content == "并发发布的目标版本"
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()



@pytest.mark.asyncio
async def test_concurrent_update_and_publish_same_draft_are_serialized(monkeypatch):
    """An update racing publication either lands before the snapshot or is rejected after it."""
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
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

        owner_id, idea_id, version_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        async with sessions() as seed:
            seed.add(User(
                id=owner_id,
                username=f"pgc_{uuid.uuid4().hex[:10]}",
                password_hash="test-only",
            ))
            await seed.flush()
            seed.add(Idea(
                id=idea_id,
                content="发布前的旧内容",
                color_hex="#123456",
                source="ugc",
                author_id=owner_id,
                border_style="gold-thin",
                publication_status="draft",
                visibility="private",
                status="active",
            ))
            await seed.flush()
            seed.add(IdeaVersion(
                id=version_id,
                idea_id=idea_id,
                version_number=1,
                content_snapshot="最初草稿内容",
                status="draft",
                created_by=owner_id,
            ))
            await seed.commit()

        async def update():
            async with sessions() as session:
                owner = await session.get(User, owner_id)
                try:
                    result = await versions_router.update_version_draft(
                        idea_id,
                        version_id,
                        VersionDraftUpdate(content="并发更新后的草稿内容"),
                        session,
                        owner,
                    )
                    return ("updated", result["status"])
                except HTTPException as exc:
                    await session.rollback()
                    return ("http_error", exc.status_code)

        async def publish():
            async with sessions() as session:
                owner = await session.get(User, owner_id)
                try:
                    result = await versions_router.publish_version(
                        idea_id, version_id, session, owner
                    )
                    return ("published", result["idea_content"])
                except HTTPException as exc:
                    await session.rollback()
                    return ("http_error", exc.status_code)

        update_outcome, publish_outcome = await asyncio.gather(update(), publish())
        assert publish_outcome[0] == "published"
        assert update_outcome in (
            ("updated", "draft"),
            ("http_error", 404),
        )

        async with sessions() as verify:
            version = await verify.get(IdeaVersion, version_id)
            idea = await verify.get(Idea, idea_id)
            assert version.status == "published"
            assert version.published_at is not None
            assert idea.content == version.content_snapshot
            if update_outcome[0] == "updated":
                assert version.content_snapshot == "并发更新后的草稿内容"
            else:
                assert version.content_snapshot == "最初草稿内容"
            draft_count = await verify.scalar(
                select(func.count()).select_from(IdeaVersion).where(
                    IdeaVersion.idea_id == idea_id,
                    IdeaVersion.status == "draft",
                )
            )
            assert draft_count == 0
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()
