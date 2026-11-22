"""PostgreSQL-only race tests for collaboration ACL and publication locks.

SQLite is deliberately excluded because it does not implement SELECT FOR UPDATE.
"""
import asyncio
import os
import uuid
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from models import (
    Base, User, Idea, Collaboration, CollaborationMember,
    CollaborationSource, CollaborationContribution,
)
from routers import collaborations as collaborations_router
from schemas.collaboration import (
    CollaborationContributionCreate, CollaborationContributionUpdate,
    CollaborationContributionReview, CollaborationPublish,
)


def _dsn():
    dsn = os.getenv("IDEAS_VERSION_CONCURRENCY_TEST_DSN")
    if not dsn:
        pytest.skip("IDEAS_VERSION_CONCURRENCY_TEST_DSN is not configured")
    if dsn.startswith("postgresql://"):
        dsn = dsn.replace("postgresql://", "postgresql+asyncpg://", 1)
    return dsn


@pytest.mark.asyncio
async def test_publish_waits_for_source_unpublish_and_rejects_new_derivative(monkeypatch):
    async def allow_audit(*args, **kwargs):
        return True, ""

    async def noop(*args, **kwargs):
        return None

    monkeypatch.setattr(collaborations_router, "audit_content", allow_audit)
    monkeypatch.setattr(collaborations_router, "write_audit_log", noop)
    monkeypatch.setattr(collaborations_router.cache, "delete", noop)
    monkeypatch.setattr(collaborations_router.cache, "delete_pattern", noop)

    engine = create_async_engine(_dsn(), pool_size=5, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

        owner_id, source_id, workspace_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        async with sessions() as seed:
            owner = User(id=owner_id, username=f"csrc_{uuid.uuid4().hex[:8]}", password_hash="test-only")
            seed.add(owner)
            await seed.flush()
            source = Idea(
                id=source_id,
                content="并发撤回测试来源",
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
                published_at=datetime.now(timezone.utc),
                legacy_license_review_status="not_required",
            )
            workspace = Collaboration(
                id=workspace_id, title="撤回竞争", owner_id=owner_id,
                status="draft", visibility="private",
            )
            seed.add_all([source, workspace])
            await seed.flush()
            seed.add(CollaborationMember(
                collaboration_id=workspace_id, user_id=owner_id,
                role="owner", status="accepted", invited_by=owner_id,
            ))
            seed.add(CollaborationSource(
                collaboration_id=workspace_id, idea_id=source_id,
                position=0, rights_snapshot={"source_idea_id": str(source_id)},
            ))
            await seed.commit()

        source_locked = asyncio.Event()
        release_unpublish = asyncio.Event()

        async def unpublish_source_first():
            async with sessions() as session:
                source = await session.scalar(
                    select(Idea).where(Idea.id == source_id).with_for_update()
                )
                source_locked.set()
                await release_unpublish.wait()
                source.publication_status = "draft"
                source.visibility = "private"
                source.allow_fork = False
                source.is_forkable = False
                await session.commit()

        async def attempt_publish():
            await source_locked.wait()
            async with sessions() as session:
                owner = await session.get(User, owner_id)
                try:
                    await collaborations_router.publish_collaboration(
                        workspace_id,
                        CollaborationPublish(
                            content="撤回之后不能发布的衍生创意",
                            visibility="public",
                            license_code="attribution_adaptation",
                            allow_fork=True,
                            confirm_terms=True,
                        ),
                        session,
                        owner,
                    )
                    return "published"
                except HTTPException as exc:
                    await session.rollback()
                    return exc.status_code

        unpublish_task = asyncio.create_task(unpublish_source_first())
        await source_locked.wait()
        publish_task = asyncio.create_task(attempt_publish())
        await asyncio.sleep(0.05)
        release_unpublish.set()
        await unpublish_task
        outcome = await publish_task
        assert outcome == 422

        async with sessions() as verify:
            count = await verify.scalar(select(func.count()).select_from(Idea))
            workspace = await verify.get(Collaboration, workspace_id)
            assert count == 1
            assert workspace.status == "draft"
            assert workspace.published_idea_id is None
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


@pytest.mark.asyncio
async def test_contribution_write_waits_for_member_revocation_and_is_denied(monkeypatch):
    engine = create_async_engine(_dsn(), pool_size=5, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    revoke_locked = asyncio.Event()
    release_revoke = asyncio.Event()

    async def pause_revocation_event(db, collaboration_id, actor_id, event_type, payload=None):
        if event_type == "member_revoked":
            revoke_locked.set()
            await release_revoke.wait()

    async def allow_audit(*args, **kwargs):
        return True, ""

    monkeypatch.setattr(collaborations_router, "_event", pause_revocation_event)
    monkeypatch.setattr(collaborations_router, "audit_content", allow_audit)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

        owner_id, contributor_id, workspace_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        async with sessions() as seed:
            seed.add_all([
                User(id=owner_id, username=f"cown_{uuid.uuid4().hex[:8]}", password_hash="test-only"),
                User(id=contributor_id, username=f"ccon_{uuid.uuid4().hex[:8]}", password_hash="test-only"),
            ])
            await seed.flush()
            seed.add(Collaboration(
                id=workspace_id, title="撤权竞争", owner_id=owner_id,
                status="draft", visibility="private",
            ))
            await seed.flush()
            seed.add_all([
                CollaborationMember(
                    collaboration_id=workspace_id, user_id=owner_id,
                    role="owner", status="accepted", invited_by=owner_id,
                ),
                CollaborationMember(
                    collaboration_id=workspace_id, user_id=contributor_id,
                    role="contributor", status="accepted", invited_by=owner_id,
                ),
            ])
            await seed.commit()

        async def revoke():
            async with sessions() as session:
                owner = await session.get(User, owner_id)
                await collaborations_router.revoke_member(
                    workspace_id, contributor_id, session, owner
                )

        async def submit():
            await revoke_locked.wait()
            async with sessions() as session:
                contributor = await session.get(User, contributor_id)
                try:
                    await collaborations_router.submit_contribution(
                        workspace_id,
                        CollaborationContributionCreate(content="撤权之后的提案"),
                        session,
                        contributor,
                    )
                    await session.commit()
                    return "submitted"
                except HTTPException as exc:
                    await session.rollback()
                    return exc.status_code

        revoke_task = asyncio.create_task(revoke())
        await revoke_locked.wait()
        submit_task = asyncio.create_task(submit())
        await asyncio.sleep(0.05)
        release_revoke.set()
        await revoke_task
        outcome = await submit_task
        assert outcome == 404

        async with sessions() as verify:
            count = await verify.scalar(
                select(func.count()).select_from(CollaborationContribution).where(
                    CollaborationContribution.collaboration_id == workspace_id
                )
            )
            member = await verify.scalar(select(CollaborationMember).where(
                CollaborationMember.collaboration_id == workspace_id,
                CollaborationMember.user_id == contributor_id,
            ))
            assert count == 0
            assert member.status == "revoked"
    finally:
        release_revoke.set()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()



@pytest.mark.asyncio
async def test_accept_waits_for_owner_revocation_and_cannot_restore_access(monkeypatch):
    engine = create_async_engine(_dsn(), pool_size=5, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    revoke_locked = asyncio.Event()
    release_revoke = asyncio.Event()

    async def pause_event(db, collaboration_id, actor_id, event_type, payload=None):
        if event_type == "member_revoked":
            revoke_locked.set()
            await release_revoke.wait()

    monkeypatch.setattr(collaborations_router, "_event", pause_event)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

        owner_id, invitee_id, workspace_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        async with sessions() as seed:
            seed.add_all([
                User(id=owner_id, username=f"arown_{uuid.uuid4().hex[:8]}", password_hash="test-only"),
                User(id=invitee_id, username=f"arinv_{uuid.uuid4().hex[:8]}", password_hash="test-only"),
                Collaboration(id=workspace_id, title="接受撤销竞争", owner_id=owner_id, status="draft", visibility="private"),
            ])
            await seed.flush()
            seed.add_all([
                CollaborationMember(collaboration_id=workspace_id, user_id=owner_id, role="owner", status="accepted", invited_by=owner_id),
                CollaborationMember(collaboration_id=workspace_id, user_id=invitee_id, role="contributor", status="pending", invited_by=owner_id),
            ])
            await seed.commit()

        async def revoke():
            async with sessions() as session:
                owner = await session.get(User, owner_id)
                return await collaborations_router.revoke_member(workspace_id, invitee_id, session, owner)

        async def accept():
            await revoke_locked.wait()
            async with sessions() as session:
                invitee = await session.get(User, invitee_id)
                try:
                    return await collaborations_router.accept_invitation(workspace_id, session, invitee)
                except HTTPException as exc:
                    await session.rollback()
                    return exc.status_code

        revoke_task = asyncio.create_task(revoke())
        await revoke_locked.wait()
        accept_task = asyncio.create_task(accept())
        await asyncio.sleep(0.05)
        release_revoke.set()
        await revoke_task
        assert await accept_task == 404

        async with sessions() as verify:
            member = await verify.scalar(select(CollaborationMember).where(
                CollaborationMember.collaboration_id == workspace_id,
                CollaborationMember.user_id == invitee_id,
            ))
            assert member.status == "revoked"
    finally:
        release_revoke.set()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


@pytest.mark.asyncio
async def test_review_waits_for_contributor_edit_and_locks_the_reviewed_snapshot(monkeypatch):
    engine = create_async_engine(_dsn(), pool_size=5, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    review_locked = asyncio.Event()
    release_review = asyncio.Event()

    async def pause_event(db, collaboration_id, actor_id, event_type, payload=None):
        if event_type == "contribution_accepted":
            review_locked.set()
            await release_review.wait()

    async def allow_audit(*args, **kwargs):
        return True, ""

    monkeypatch.setattr(collaborations_router, "_event", pause_event)
    monkeypatch.setattr(collaborations_router, "audit_content", allow_audit)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

        owner_id, contributor_id, workspace_id, contribution_id = (
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        )
        async with sessions() as seed:
            seed.add_all([
                User(id=owner_id, username=f"rvown_{uuid.uuid4().hex[:8]}", password_hash="test-only"),
                User(id=contributor_id, username=f"rvcon_{uuid.uuid4().hex[:8]}", password_hash="test-only"),
                Collaboration(id=workspace_id, title="审核编辑竞争", owner_id=owner_id, status="draft", visibility="private"),
            ])
            await seed.flush()
            seed.add_all([
                CollaborationMember(collaboration_id=workspace_id, user_id=owner_id, role="owner", status="accepted", invited_by=owner_id),
                CollaborationMember(collaboration_id=workspace_id, user_id=contributor_id, role="contributor", status="accepted", invited_by=owner_id),
                CollaborationContribution(id=contribution_id, collaboration_id=workspace_id, author_id=contributor_id, content="审核时的原始内容", status="submitted"),
            ])
            await seed.commit()

        async def review():
            async with sessions() as session:
                owner = await session.get(User, owner_id)
                return await collaborations_router.review_contribution(
                    workspace_id, contribution_id,
                    CollaborationContributionReview(decision="accepted"),
                    session, owner,
                )

        async def edit():
            await review_locked.wait()
            async with sessions() as session:
                contributor = await session.get(User, contributor_id)
                try:
                    return await collaborations_router.update_contribution(
                        workspace_id, contribution_id,
                        CollaborationContributionUpdate(content="审核之后的编辑内容"),
                        session, contributor,
                    )
                except HTTPException as exc:
                    await session.rollback()
                    return exc.status_code

        review_task = asyncio.create_task(review())
        await review_locked.wait()
        edit_task = asyncio.create_task(edit())
        await asyncio.sleep(0.05)
        release_review.set()
        await review_task
        assert await edit_task == 404

        async with sessions() as verify:
            item = await verify.get(CollaborationContribution, contribution_id)
            assert item.status == "accepted"
            assert item.content == "审核时的原始内容"
    finally:
        release_review.set()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


@pytest.mark.asyncio
async def test_member_leave_serializes_before_and_blocks_contribution_write(monkeypatch):
    engine = create_async_engine(_dsn(), pool_size=5, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    leave_locked = asyncio.Event()
    release_leave = asyncio.Event()

    async def pause_event(db, collaboration_id, actor_id, event_type, payload=None):
        if event_type == "member_left":
            leave_locked.set()
            await release_leave.wait()

    async def allow_audit(*args, **kwargs):
        return True, ""

    monkeypatch.setattr(collaborations_router, "_event", pause_event)
    monkeypatch.setattr(collaborations_router, "audit_content", allow_audit)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

        owner_id, contributor_id, workspace_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        async with sessions() as seed:
            seed.add_all([
                User(id=owner_id, username=f"lvown_{uuid.uuid4().hex[:8]}", password_hash="test-only"),
                User(id=contributor_id, username=f"lvcon_{uuid.uuid4().hex[:8]}", password_hash="test-only"),
                Collaboration(id=workspace_id, title="主动离开竞争", owner_id=owner_id, status="draft", visibility="private"),
            ])
            await seed.flush()
            seed.add_all([
                CollaborationMember(collaboration_id=workspace_id, user_id=owner_id, role="owner", status="accepted", invited_by=owner_id),
                CollaborationMember(collaboration_id=workspace_id, user_id=contributor_id, role="contributor", status="accepted", invited_by=owner_id),
            ])
            await seed.commit()

        async def leave():
            async with sessions() as session:
                contributor = await session.get(User, contributor_id)
                return await collaborations_router.leave_collaboration(workspace_id, session, contributor)

        async def submit():
            await leave_locked.wait()
            async with sessions() as session:
                contributor = await session.get(User, contributor_id)
                try:
                    return await collaborations_router.submit_contribution(
                        workspace_id,
                        CollaborationContributionCreate(content="离开之后的提交"),
                        session, contributor,
                    )
                except HTTPException as exc:
                    await session.rollback()
                    return exc.status_code

        leave_task = asyncio.create_task(leave())
        await leave_locked.wait()
        submit_task = asyncio.create_task(submit())
        await asyncio.sleep(0.05)
        release_leave.set()
        await leave_task
        assert await submit_task == 404

        async with sessions() as verify:
            count = await verify.scalar(select(func.count()).select_from(CollaborationContribution))
            member = await verify.scalar(select(CollaborationMember).where(
                CollaborationMember.collaboration_id == workspace_id,
                CollaborationMember.user_id == contributor_id,
            ))
            assert count == 0
            assert member.status == "left"
    finally:
        release_leave.set()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


@pytest.mark.asyncio
async def test_archive_serializes_before_and_blocks_contribution_write(monkeypatch):
    engine = create_async_engine(_dsn(), pool_size=5, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    archive_locked = asyncio.Event()
    release_archive = asyncio.Event()

    async def pause_event(db, collaboration_id, actor_id, event_type, payload=None):
        if event_type == "collaboration_archived":
            archive_locked.set()
            await release_archive.wait()

    async def allow_audit(*args, **kwargs):
        return True, ""

    monkeypatch.setattr(collaborations_router, "_event", pause_event)
    monkeypatch.setattr(collaborations_router, "audit_content", allow_audit)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

        owner_id, contributor_id, workspace_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        async with sessions() as seed:
            seed.add_all([
                User(id=owner_id, username=f"arown_{uuid.uuid4().hex[:8]}", password_hash="test-only"),
                User(id=contributor_id, username=f"arcon_{uuid.uuid4().hex[:8]}", password_hash="test-only"),
                Collaboration(id=workspace_id, title="归档写入竞争", owner_id=owner_id, status="draft", visibility="private"),
            ])
            await seed.flush()
            seed.add_all([
                CollaborationMember(collaboration_id=workspace_id, user_id=owner_id, role="owner", status="accepted", invited_by=owner_id),
                CollaborationMember(collaboration_id=workspace_id, user_id=contributor_id, role="contributor", status="accepted", invited_by=owner_id),
            ])
            await seed.commit()

        async def archive():
            async with sessions() as session:
                owner = await session.get(User, owner_id)
                return await collaborations_router.archive_collaboration(workspace_id, session, owner)

        async def submit():
            await archive_locked.wait()
            async with sessions() as session:
                contributor = await session.get(User, contributor_id)
                try:
                    return await collaborations_router.submit_contribution(
                        workspace_id,
                        CollaborationContributionCreate(content="归档之后的提交"),
                        session, contributor,
                    )
                except HTTPException as exc:
                    await session.rollback()
                    return exc.status_code

        archive_task = asyncio.create_task(archive())
        await archive_locked.wait()
        submit_task = asyncio.create_task(submit())
        await asyncio.sleep(0.05)
        release_archive.set()
        await archive_task
        assert await submit_task == 409

        async with sessions() as verify:
            workspace = await verify.get(Collaboration, workspace_id)
            count = await verify.scalar(select(func.count()).select_from(CollaborationContribution))
            assert workspace.status == "archived"
            assert count == 0
    finally:
        release_archive.set()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()
