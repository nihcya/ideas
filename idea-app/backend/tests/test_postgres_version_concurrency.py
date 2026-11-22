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

from models import Base, User, Idea, IdeaVersion, IdeaContribution, IdeaVersionContribution, IdeaAccessGrant, ForkRelation
from routers import idea_versions as versions_router
from routers import ideas as ideas_router
from schemas.idea import IdeaContributionUpdate, IdeaContributionReview, IdeaForkRequest
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


@pytest.mark.asyncio
async def test_concurrent_contribution_review_and_edit_are_serialized(monkeypatch):
    """Review and contributor edit serialize on the contribution row."""
    dsn = os.getenv("IDEAS_VERSION_CONCURRENCY_TEST_DSN")
    if not dsn:
        pytest.skip("IDEAS_VERSION_CONCURRENCY_TEST_DSN is not configured")
    if dsn.startswith("postgresql://"):
        dsn = dsn.replace("postgresql://", "postgresql+asyncpg://", 1)

    async def allow_audit(*args, **kwargs):
        return True, ""

    async def noop_audit_log(*args, **kwargs):
        return None

    monkeypatch.setattr(ideas_router, "audit_content", allow_audit)
    monkeypatch.setattr(ideas_router, "write_audit_log", noop_audit_log)

    engine = create_async_engine(dsn, pool_size=5, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

        owner_id, contributor_id = uuid.uuid4(), uuid.uuid4()
        idea_id, contribution_id, grant_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        async with sessions() as seed:
            seed.add_all([
                User(id=owner_id, username=f"pgo_{uuid.uuid4().hex[:10]}", password_hash="test-only"),
                User(id=contributor_id, username=f"pgc_{uuid.uuid4().hex[:10]}", password_hash="test-only"),
            ])
            await seed.flush()
            seed.add(Idea(
                id=idea_id,
                content="协作贡献并发测试",
                color_hex="#123456",
                source="ugc",
                author_id=owner_id,
                border_style="gold-thin",
                publication_status="draft",
                visibility="private",
                status="active",
            ))
            await seed.flush()
            seed.add(IdeaAccessGrant(
                id=grant_id,
                idea_id=idea_id,
                user_id=contributor_id,
                role="contributor",
                status="accepted",
                invited_by=owner_id,
            ))
            seed.add(IdeaContribution(
                id=contribution_id,
                idea_id=idea_id,
                author_id=contributor_id,
                content="审核前的原始贡献",
                status="submitted",
            ))
            await seed.commit()

        async def edit():
            async with sessions() as session:
                contributor = await session.get(User, contributor_id)
                try:
                    result = await ideas_router.update_idea_contribution(
                        idea_id,
                        contribution_id,
                        IdeaContributionUpdate(content="并发编辑后的贡献"),
                        session,
                        contributor,
                    )
                    return ("updated", result["status"])
                except HTTPException as exc:
                    await session.rollback()
                    return ("http_error", exc.status_code)

        async def review():
            async with sessions() as session:
                owner = await session.get(User, owner_id)
                try:
                    result = await ideas_router.review_idea_contribution(
                        idea_id,
                        contribution_id,
                        IdeaContributionReview(decision="accepted"),
                        session,
                        owner,
                    )
                    return ("reviewed", result["status"])
                except HTTPException as exc:
                    await session.rollback()
                    return ("http_error", exc.status_code)

        edit_outcome, review_outcome = await asyncio.gather(edit(), review())
        assert review_outcome == ("reviewed", "accepted")
        assert edit_outcome in (
            ("updated", "submitted"),
            ("http_error", 404),
        )

        async with sessions() as verify:
            contribution = await verify.get(IdeaContribution, contribution_id)
            assert contribution.status == "accepted"
            assert contribution.reviewed_by == owner_id
            assert contribution.reviewed_at is not None
            if edit_outcome[0] == "updated":
                assert contribution.content == "并发编辑后的贡献"
            else:
                assert contribution.content == "审核前的原始贡献"
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_contribution_edit_and_invite_revocation_are_serialized(monkeypatch):
    """An edit either commits before revocation or is denied after revocation."""
    dsn = os.getenv("IDEAS_VERSION_CONCURRENCY_TEST_DSN")
    if not dsn:
        pytest.skip("IDEAS_VERSION_CONCURRENCY_TEST_DSN is not configured")
    if dsn.startswith("postgresql://"):
        dsn = dsn.replace("postgresql://", "postgresql+asyncpg://", 1)

    async def allow_audit(*args, **kwargs):
        return True, ""

    async def noop_audit_log(*args, **kwargs):
        return None

    monkeypatch.setattr(ideas_router, "audit_content", allow_audit)
    monkeypatch.setattr(ideas_router, "write_audit_log", noop_audit_log)
    monkeypatch.setattr(ideas_router.cache, "delete", noop_audit_log)

    engine = create_async_engine(dsn, pool_size=5, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

        owner_id, contributor_id = uuid.uuid4(), uuid.uuid4()
        idea_id, contribution_id, grant_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        async with sessions() as seed:
            seed.add_all([
                User(id=owner_id, username=f"pgo_{uuid.uuid4().hex[:10]}", password_hash="test-only"),
                User(id=contributor_id, username=f"pgc_{uuid.uuid4().hex[:10]}", password_hash="test-only"),
            ])
            await seed.flush()
            seed.add(Idea(
                id=idea_id,
                content="撤销邀请并发测试",
                color_hex="#123456",
                source="ugc",
                author_id=owner_id,
                border_style="gold-thin",
                publication_status="draft",
                visibility="private",
                status="active",
            ))
            await seed.flush()
            seed.add(IdeaAccessGrant(
                id=grant_id,
                idea_id=idea_id,
                user_id=contributor_id,
                role="contributor",
                status="accepted",
                invited_by=owner_id,
            ))
            seed.add(IdeaContribution(
                id=contribution_id,
                idea_id=idea_id,
                author_id=contributor_id,
                content="撤权前的贡献",
                status="submitted",
            ))
            await seed.commit()

        async def edit():
            async with sessions() as session:
                contributor = await session.get(User, contributor_id)
                try:
                    result = await ideas_router.update_idea_contribution(
                        idea_id,
                        contribution_id,
                        IdeaContributionUpdate(content="撤权竞争中的编辑"),
                        session,
                        contributor,
                    )
                    return ("updated", result["status"])
                except HTTPException as exc:
                    await session.rollback()
                    return ("http_error", exc.status_code)

        async def revoke():
            async with sessions() as session:
                owner = await session.get(User, owner_id)
                try:
                    result = await ideas_router.revoke_private_idea_invite(
                        idea_id, grant_id, session, owner
                    )
                    return ("revoked", result["revoked"])
                except HTTPException as exc:
                    await session.rollback()
                    return ("http_error", exc.status_code)

        edit_outcome, revoke_outcome = await asyncio.gather(edit(), revoke())
        assert revoke_outcome == ("revoked", True)
        assert edit_outcome in (
            ("updated", "submitted"),
            ("http_error", 403),
        )

        async with sessions() as verify:
            grant = await verify.get(IdeaAccessGrant, grant_id)
            contribution = await verify.get(IdeaContribution, contribution_id)
            assert grant.status == "revoked"
            if edit_outcome[0] == "updated":
                assert contribution.content == "撤权竞争中的编辑"
            else:
                assert contribution.content == "撤权前的贡献"
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_fork_and_source_unpublish_are_serialized(monkeypatch):
    """A fork must commit before unpublish, or fail after unpublish; never after rights expire."""
    dsn = os.getenv("IDEAS_VERSION_CONCURRENCY_TEST_DSN")
    if not dsn:
        pytest.skip("IDEAS_VERSION_CONCURRENCY_TEST_DSN is not configured")
    if dsn.startswith("postgresql://"):
        dsn = dsn.replace("postgresql://", "postgresql+asyncpg://", 1)

    audit_entered = asyncio.Event()
    allow_fork_to_finish = asyncio.Event()
    unpublish_started = asyncio.Event()

    async def blocked_audit(*args, **kwargs):
        audit_entered.set()
        await allow_fork_to_finish.wait()
        return True, ""

    async def noop(*args, **kwargs):
        return None

    monkeypatch.setattr(ideas_router, "audit_content", blocked_audit)
    monkeypatch.setattr(ideas_router.cache, "delete_pattern", noop)
    monkeypatch.setattr(ideas_router.cache, "delete", noop)

    engine = create_async_engine(dsn, pool_size=5, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

        owner_id, forker_id, source_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        async with sessions() as seed:
            seed.add_all([
                User(id=owner_id, username=f"pgo_{uuid.uuid4().hex[:10]}", password_hash="test-only"),
                User(id=forker_id, username=f"pgf_{uuid.uuid4().hex[:10]}", password_hash="test-only"),
            ])
            await seed.flush()
            seed.add(Idea(
                id=source_id,
                content="并发撤回测试的公开来源",
                color_hex="#123456",
                source="ugc",
                author_id=owner_id,
                border_style="gold-thin",
                publication_status="published",
                visibility="public",
                license_code="attribution_adaptation",
                license_version="v1",
                allow_fork=True,
                is_forkable=True,
                legacy_license_review_status="confirmed",
                status="active",
            ))
            await seed.commit()

        async def fork():
            async with sessions() as session:
                forker = await session.get(User, forker_id)
                try:
                    result = await ideas_router.fork_idea(
                        IdeaForkRequest(
                            parent_id=str(source_id),
                            content="在来源撤回前已经开始的衍生创意",
                        ),
                        session,
                        forker,
                    )
                    return ("forked", result.id)
                except HTTPException as exc:
                    await session.rollback()
                    return ("http_error", exc.status_code)

        async def unpublish():
            async with sessions() as session:
                owner = await session.get(User, owner_id)
                unpublish_started.set()
                try:
                    await ideas_router.unpublish_idea(source_id, session, owner)
                    return ("unpublished", True)
                except HTTPException as exc:
                    await session.rollback()
                    return ("http_error", exc.status_code)

        fork_task = asyncio.create_task(fork())
        await asyncio.wait_for(audit_entered.wait(), timeout=10)
        unpublish_task = asyncio.create_task(unpublish())
        await asyncio.wait_for(unpublish_started.wait(), timeout=10)
        await asyncio.sleep(0.05)
        assert not unpublish_task.done(), "unpublish must wait for the in-flight derivation lock"

        allow_fork_to_finish.set()
        fork_outcome, unpublish_outcome = await asyncio.gather(fork_task, unpublish_task)
        assert fork_outcome[0] == "forked"
        assert unpublish_outcome == ("unpublished", True)

        async with sessions() as verify:
            source = await verify.get(Idea, source_id)
            assert source.visibility == "private"
            assert source.publication_status == "draft"
            relation = await verify.scalar(
                select(ForkRelation).where(
                    ForkRelation.child_id == uuid.UUID(fork_outcome[1]),
                    ForkRelation.parent_id == source_id,
                )
            )
            assert relation is not None
            assert relation.license_snapshot["source_author_name"] is not None
            assert relation.license_snapshot["license_code"] == "attribution_adaptation"
    finally:
        if not allow_fork_to_finish.is_set():
            allow_fork_to_finish.set()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()
