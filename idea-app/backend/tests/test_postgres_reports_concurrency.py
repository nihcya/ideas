"""PostgreSQL race regression for concurrent duplicate Idea reports."""
import asyncio
import os
import uuid
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from deps import get_current_user, get_db
from main import app
from models import Base, User, Idea, IdeaReport
from routers import reports as reports_router


def _dsn():
    value = os.getenv("IDEAS_VERSION_CONCURRENCY_TEST_DSN")
    if not value:
        pytest.skip("IDEAS_VERSION_CONCURRENCY_TEST_DSN is not configured")
    if value.startswith("postgresql://"):
        value = value.replace("postgresql://", "postgresql+asyncpg://", 1)
    return value


@pytest.mark.asyncio
async def test_simultaneous_report_submissions_return_one_created_and_one_conflict(monkeypatch):
    engine = create_async_engine(_dsn(), pool_size=5, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    both_checked_acl = asyncio.Event()
    acl_calls = 0

    async def synchronized_acl(*args, **kwargs):
        nonlocal acl_calls
        acl_calls += 1
        if acl_calls == 2:
            both_checked_acl.set()
        await both_checked_acl.wait()
        return True

    monkeypatch.setattr(reports_router, "can_view_idea", synchronized_acl)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

        owner_id, reporter_id, idea_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        async with sessions() as seed:
            owner = User(
                id=owner_id,
                username=f"rpo_{uuid.uuid4().hex[:8]}",
                password_hash="test-only",
            )
            reporter = User(
                id=reporter_id,
                username=f"rpr_{uuid.uuid4().hex[:8]}",
                password_hash="test-only",
            )
            seed.add_all([owner, reporter])
            await seed.flush()
            seed.add(Idea(
                id=idea_id,
                content="并发举报目标",
                color_hex="#123456",
                source="ugc",
                author_id=owner_id,
                border_style="gold-thin",
                status="active",
                publication_status="published",
                visibility="public",
                license_code="attribution",
                license_version="v1",
                allow_fork=True,
                is_forkable=True,
                published_at=datetime.now(timezone.utc),
                legacy_license_review_status="not_required",
            ))
            await seed.commit()

        async def override_db():
            async with sessions() as session:
                yield session

        async def override_user():
            async with sessions() as session:
                return await session.get(User, reporter_id)

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = override_user
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                responses = await asyncio.gather(
                    client.post("/api/reports", json={
                        "idea_id": str(idea_id),
                        "reason": "copyright",
                        "description": "并发请求 A",
                    }),
                    client.post("/api/reports", json={
                        "idea_id": str(idea_id),
                        "reason": "spam",
                        "description": "并发请求 B",
                    }),
                )
            assert sorted(response.status_code for response in responses) == [201, 409]
            async with sessions() as verify:
                rows = (await verify.execute(
                    __import__("sqlalchemy").select(IdeaReport).where(
                        IdeaReport.idea_id == idea_id,
                        IdeaReport.reporter_id == reporter_id,
                        IdeaReport.status.in_(["pending", "in_review"]),
                    )
                )).scalars().all()
                assert len(rows) == 1
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(get_current_user, None)
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()
