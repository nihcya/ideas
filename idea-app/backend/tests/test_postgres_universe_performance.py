"""PostgreSQL graph traversal safety and index-plan regression tests.

Runs only against a disposable PostgreSQL 16 CI database. It deliberately
avoids wall-clock assertions: query plans and bounded traversal are stable
contracts, while elapsed time is too environment-dependent for CI.
"""
import os
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from models import Base, User, Idea, ForkRelation, IdeaAssociation
from routers.universe import get_idea_graph


def _dsn():
    value = os.getenv("IDEAS_UNIVERSE_TEST_DSN")
    if not value:
        pytest.skip("IDEAS_UNIVERSE_TEST_DSN is not configured")
    if value.startswith("postgresql://"):
        value = value.replace("postgresql://", "postgresql+asyncpg://", 1)
    return value


def _public_idea(owner_id, content):
    return Idea(
        content=content,
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


@pytest.mark.asyncio
async def test_graph_traversal_terminates_on_historical_cycle_and_stays_bounded():
    engine = create_async_engine(_dsn(), pool_size=5, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

        owner_id = uuid.uuid4()
        idea_ids = [uuid.uuid4() for _ in range(3)]
        async with sessions() as seed:
            seed.add(User(
                id=owner_id,
                username=f"universe_{uuid.uuid4().hex[:10]}",
                password_hash="test-only",
            ))
            await seed.flush()
            ideas = [
                _public_idea(owner_id, f"循环图节点 {index}")
                for index in range(3)
            ]
            for idea, idea_id in zip(ideas, idea_ids):
                idea.id = idea_id
            seed.add_all(ideas)
            await seed.flush()
            seed.add_all([
                ForkRelation(
                    parent_id=idea_ids[0], child_id=idea_ids[1],
                    relation_type="fork", license_snapshot={"source_author_name": "测试作者"},
                ),
                ForkRelation(
                    parent_id=idea_ids[1], child_id=idea_ids[2],
                    relation_type="evolve", license_snapshot={"source_author_name": "测试作者"},
                ),
                # Deliberately malformed historical edge: the API must still terminate.
                ForkRelation(
                    parent_id=idea_ids[2], child_id=idea_ids[0],
                    relation_type="merge", license_snapshot={"source_author_name": "测试作者"},
                ),
            ])
            await seed.commit()

        async with sessions() as session:
            owner = await session.get(User, owner_id)
            graph = await get_idea_graph(
                idea_ids[0], 3, "both", False, 100, session, owner
            )
            node_ids = {node["id"] for node in graph["nodes"]}
            assert node_ids == {str(value) for value in idea_ids}
            assert len(graph["nodes"]) == 3
            assert len(graph["edges"]) == 3
            assert graph["truncated"] is False
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


@pytest.mark.asyncio
async def test_graph_traversal_indexes_are_used_for_both_directions():
    engine = create_async_engine(_dsn(), pool_size=5, max_overflow=0)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

        owner_id = uuid.uuid4()
        idea_ids = [uuid.uuid4() for _ in range(701)]
        async with sessions() as seed:
            seed.add(User(
                id=owner_id,
                username=f"universe_idx_{uuid.uuid4().hex[:10]}",
                password_hash="test-only",
            ))
            await seed.flush()
            ideas = [
                _public_idea(owner_id, f"索引基准节点 {index}")
                for index in range(len(idea_ids))
            ]
            for idea, idea_id in zip(ideas, idea_ids):
                idea.id = idea_id
            seed.add_all(ideas)
            await seed.flush()
            seed.add_all([
                ForkRelation(
                    parent_id=idea_ids[index],
                    child_id=idea_ids[index + 1],
                    relation_type="fork",
                    license_snapshot={"source_author_name": "索引测试"},
                )
                for index in range(600)
            ])
            seed.add_all([
                IdeaAssociation(
                    source_idea_id=idea_ids[index],
                    target_idea_id=idea_ids[index + 1],
                    relation_type="inspired",
                    created_by=owner_id,
                )
                for index in range(100)
            ])
            await seed.commit()

        async with engine.begin() as conn:
            await conn.execute(text("ANALYZE fork_relations"))
            await conn.execute(text("ANALYZE idea_associations"))
            await conn.execute(text("SET LOCAL enable_seqscan = off"))
            plans = {}
            queries = {
                "lineage_by_child": (
                    "EXPLAIN (COSTS OFF) SELECT id FROM fork_relations "
                    "WHERE child_id = CAST(:idea_id AS UUID)"
                ),
                "lineage_by_parent": (
                    "EXPLAIN (COSTS OFF) SELECT id FROM fork_relations "
                    "WHERE parent_id = CAST(:idea_id AS UUID)"
                ),
                "inspired_by_source": (
                    "EXPLAIN (COSTS OFF) SELECT id FROM idea_associations "
                    "WHERE source_idea_id = CAST(:idea_id AS UUID)"
                ),
                "inspired_by_target": (
                    "EXPLAIN (COSTS OFF) SELECT id FROM idea_associations "
                    "WHERE target_idea_id = CAST(:idea_id AS UUID)"
                ),
            }
            for key, sql in queries.items():
                result = await conn.execute(
                    text(sql), {"idea_id": str(idea_ids[350])}
                )
                plans[key] = "\n".join(row[0] for row in result.fetchall())

        assert "ix_fork_relations_child_id" in plans["lineage_by_child"]
        assert "ix_fork_relations_parent_id" in plans["lineage_by_parent"]
        assert "idx_idea_associations_source" in plans["inspired_by_source"]
        assert "idx_idea_associations_target" in plans["inspired_by_target"]
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()
