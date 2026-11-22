"""Real PostgreSQL 16 integration test for the manual V2 schema migrations.

Runs only when IDEAS_MIGRATION_TEST_DSN points at a disposable test database.
CI provides an isolated PostgreSQL service; this test never targets production.
"""
import os
from pathlib import Path
import uuid

import asyncpg
import pytest


MIGRATIONS = Path(__file__).resolve().parent.parent / "migrations"


@pytest.mark.asyncio
async def test_postgres_16_migrations_apply_in_order_and_enforce_constraints():
    dsn = os.getenv("IDEAS_MIGRATION_TEST_DSN")
    if not dsn:
        pytest.skip("IDEAS_MIGRATION_TEST_DSN is not configured")

    conn = await asyncpg.connect(dsn)
    try:
        # The CI service database is disposable and dedicated to this test.
        await conn.execute("""
            DROP TABLE IF EXISTS idea_version_contributions CASCADE;
            DROP TABLE IF EXISTS idea_versions CASCADE;
            DROP TABLE IF EXISTS idea_contributions CASCADE;
            DROP TABLE IF EXISTS idea_access_grants CASCADE;
            DROP TABLE IF EXISTS app_schema_migrations CASCADE;
            DROP TABLE IF EXISTS fork_relations CASCADE;
            DROP TABLE IF EXISTS ideas CASCADE;
            DROP TABLE IF EXISTS users CASCADE;

            CREATE TABLE users (
                id UUID PRIMARY KEY
            );
            CREATE TABLE ideas (
                id UUID PRIMARY KEY,
                status VARCHAR(16) NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                is_forkable BOOLEAN NOT NULL DEFAULT FALSE
            );
            CREATE TABLE fork_relations (
                id UUID PRIMARY KEY
            );
        """)

        owner_id = uuid.uuid4()
        contributor_id = uuid.uuid4()
        active_idea_id = uuid.uuid4()
        draft_idea_id = uuid.uuid4()
        await conn.executemany(
            "INSERT INTO users(id) VALUES($1)",
            [(owner_id,), (contributor_id,)],
        )
        await conn.executemany(
            "INSERT INTO ideas(id, status) VALUES($1, $2)",
            [(active_idea_id, "active"), (draft_idea_id, "draft")],
        )

        for name in (
            "001_idea_visibility_and_acl.sql",
            "002_idea_contributions.sql",
            "003_idea_versions_and_attribution.sql",
        ):
            sql = (MIGRATIONS / name).read_text(encoding="utf-8")
            await conn.execute(sql)

        markers = await conn.fetch(
            "SELECT version FROM app_schema_migrations ORDER BY version"
        )
        assert {row["version"] for row in markers} == {
            "001_idea_visibility_and_acl",
            "002_idea_contributions",
            "003_idea_versions_and_attribution",
        }

        active = await conn.fetchrow(
            "SELECT publication_status, visibility, legacy_license_review_status, allow_fork "
            "FROM ideas WHERE id = $1",
            active_idea_id,
        )
        assert tuple(active) == ("published", "public", "pending", False)

        draft = await conn.fetchrow(
            "SELECT publication_status, visibility FROM ideas WHERE id = $1",
            draft_idea_id,
        )
        assert tuple(draft) == ("draft", "private")

        contribution_id = uuid.uuid4()
        version_one_id = uuid.uuid4()
        version_two_id = uuid.uuid4()
        await conn.execute(
            "INSERT INTO idea_contributions(id, idea_id, author_id, content, status) "
            "VALUES($1, $2, $3, $4, 'accepted')",
            contribution_id, active_idea_id, contributor_id, "frozen contribution",
        )
        await conn.execute(
            "INSERT INTO idea_versions(id, idea_id, version_number, content_snapshot, status, created_by) "
            "VALUES($1, $2, 1, 'v1', 'published', $3)",
            version_one_id, active_idea_id, owner_id,
        )
        await conn.execute(
            "INSERT INTO idea_versions(id, idea_id, version_number, content_snapshot, status, created_by) "
            "VALUES($1, $2, 2, 'v2', 'draft', $3)",
            version_two_id, active_idea_id, owner_id,
        )
        await conn.execute(
            "INSERT INTO idea_version_contributions"
            "(version_id, contribution_id, author_id_snapshot, author_name_snapshot, content_snapshot) "
            "VALUES($1, $2, $3, 'contributor', 'frozen contribution')",
            version_one_id, contribution_id, contributor_id,
        )

        with pytest.raises(asyncpg.UniqueViolationError):
            await conn.execute(
                "INSERT INTO idea_versions(id, idea_id, version_number, content_snapshot, status, created_by) "
                "VALUES($1, $2, 1, 'duplicate number', 'draft', $3)",
                uuid.uuid4(), active_idea_id, owner_id,
            )

        with pytest.raises(asyncpg.UniqueViolationError):
            await conn.execute(
                "INSERT INTO idea_version_contributions"
                "(version_id, contribution_id, author_id_snapshot, author_name_snapshot, content_snapshot) "
                "VALUES($1, $2, $3, 'contributor', 'duplicate attribution')",
                version_two_id, contribution_id, contributor_id,
            )

    finally:
        await conn.close()
