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
            DROP TABLE IF EXISTS user_follows CASCADE;
            DROP TABLE IF EXISTS idea_reports CASCADE;
            DROP TABLE IF EXISTS notification_preferences CASCADE;
            DROP TABLE IF EXISTS idea_associations CASCADE;
            DROP TABLE IF EXISTS notifications CASCADE;
            DROP TABLE IF EXISTS collaboration_events CASCADE;
            DROP TABLE IF EXISTS collaboration_contributions CASCADE;
            DROP TABLE IF EXISTS collaboration_sources CASCADE;
            DROP TABLE IF EXISTS collaboration_members CASCADE;
            DROP TABLE IF EXISTS collaborations CASCADE;
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
            CREATE TABLE notifications (
                id UUID PRIMARY KEY,
                user_id UUID,
                type VARCHAR(20) NOT NULL,
                content VARCHAR(200) NOT NULL,
                idea_id UUID,
                actor_id UUID,
                read BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
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
            "004_collaborations.sql",
            "005_collaboration_attribution.sql",
            "006_idea_associations.sql",
            "007_notification_preferences.sql",
            "008_collaboration_member_leave.sql",
            "009_collaboration_notification_links.sql",
            "010_idea_reports.sql",
            "011_user_follows.sql",
            "012_legacy_license_deadlines.sql",
            "013_notification_type_length.sql",
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
            "004_collaborations",
            "005_collaboration_attribution",
            "006_idea_associations",
            "007_notification_preferences",
            "008_collaboration_member_leave",
            "009_collaboration_notification_links",
            "010_idea_reports",
            "011_user_follows",
            "012_legacy_license_deadlines",
            "013_notification_type_length",
        }

        active = await conn.fetchrow(
            "SELECT publication_status, visibility, legacy_license_review_status, allow_fork "
            "FROM ideas WHERE id = $1",
            active_idea_id,
        )
        assert tuple(active) == ("published", "public", "pending", False)
        activation_at = await conn.fetchval(
            "SELECT applied_at FROM app_schema_migrations WHERE version='001_idea_visibility_and_acl'"
        )
        legacy_due_at = await conn.fetchval(
            "SELECT legacy_license_review_due_at FROM ideas WHERE id=$1", active_idea_id
        )
        assert abs((legacy_due_at - activation_at).total_seconds() - 90 * 24 * 60 * 60) < 2

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


@pytest.mark.asyncio
async def test_postgres_migration_order_guards_and_failed_transaction_rollback():
    dsn = os.getenv("IDEAS_MIGRATION_TEST_DSN")
    if not dsn:
        pytest.skip("IDEAS_MIGRATION_TEST_DSN is not configured")

    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute("""
            DROP TABLE IF EXISTS user_follows CASCADE;
            DROP TABLE IF EXISTS idea_reports CASCADE;
            DROP TABLE IF EXISTS notification_preferences CASCADE;
            DROP TABLE IF EXISTS idea_associations CASCADE;
            DROP TABLE IF EXISTS notifications CASCADE;
            DROP TABLE IF EXISTS collaboration_events CASCADE;
            DROP TABLE IF EXISTS collaboration_contributions CASCADE;
            DROP TABLE IF EXISTS collaboration_sources CASCADE;
            DROP TABLE IF EXISTS collaboration_members CASCADE;
            DROP TABLE IF EXISTS collaborations CASCADE;
            DROP TABLE IF EXISTS idea_version_contributions CASCADE;
            DROP TABLE IF EXISTS idea_versions CASCADE;
            DROP TABLE IF EXISTS idea_contributions CASCADE;
            DROP TABLE IF EXISTS idea_access_grants CASCADE;
            DROP TABLE IF EXISTS app_schema_migrations CASCADE;
            DROP TABLE IF EXISTS fork_relations CASCADE;
            DROP TABLE IF EXISTS ideas CASCADE;
            DROP TABLE IF EXISTS users CASCADE;

            CREATE TABLE users (id UUID PRIMARY KEY);
            CREATE TABLE ideas (
                id UUID PRIMARY KEY,
                status VARCHAR(16) NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                is_forkable BOOLEAN NOT NULL DEFAULT FALSE
            );
            CREATE TABLE fork_relations (id UUID PRIMARY KEY);
            CREATE TABLE notifications (
                id UUID PRIMARY KEY, user_id UUID, type VARCHAR(20) NOT NULL,
                content VARCHAR(200) NOT NULL, idea_id UUID, actor_id UUID,
                read BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
        """)

        migration_001 = (MIGRATIONS / "001_idea_visibility_and_acl.sql").read_text(encoding="utf-8")
        migration_002 = (MIGRATIONS / "002_idea_contributions.sql").read_text(encoding="utf-8")
        migration_003 = (MIGRATIONS / "003_idea_versions_and_attribution.sql").read_text(encoding="utf-8")
        migration_004 = (MIGRATIONS / "004_collaborations.sql").read_text(encoding="utf-8")
        migration_005 = (MIGRATIONS / "005_collaboration_attribution.sql").read_text(encoding="utf-8")
        migration_006 = (MIGRATIONS / "006_idea_associations.sql").read_text(encoding="utf-8")
        migration_007 = (MIGRATIONS / "007_notification_preferences.sql").read_text(encoding="utf-8")
        migration_008 = (MIGRATIONS / "008_collaboration_member_leave.sql").read_text(encoding="utf-8")
        migration_009 = (MIGRATIONS / "009_collaboration_notification_links.sql").read_text(encoding="utf-8")
        migration_010 = (MIGRATIONS / "010_idea_reports.sql").read_text(encoding="utf-8")
        migration_011 = (MIGRATIONS / "011_user_follows.sql").read_text(encoding="utf-8")
        migration_012 = (MIGRATIONS / "012_legacy_license_deadlines.sql").read_text(encoding="utf-8")
        migration_013 = (MIGRATIONS / "013_notification_type_length.sql").read_text(encoding="utf-8")

        async def expect_migration_failure(sql):
            with pytest.raises(asyncpg.PostgresError):
                await conn.execute(sql)
            # asyncpg leaves the failed multi-statement transaction aborted until rollback.
            await conn.execute("ROLLBACK")

        # Migration 002 must fail before 001, and its transaction must leave no table behind.
        await expect_migration_failure(migration_002)
        assert await conn.fetchval("SELECT to_regclass('public.app_schema_migrations')") is None
        assert await conn.fetchval("SELECT to_regclass('public.idea_contributions')") is None

        await conn.execute(migration_001)

        # Migration 001 is intentionally one-shot; a second attempt must fail cleanly.
        await expect_migration_failure(migration_001)
        markers = await conn.fetch("SELECT version FROM app_schema_migrations")
        assert [row["version"] for row in markers] == ["001_idea_visibility_and_acl"]
        assert await conn.fetchval(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name='ideas' "
            "AND column_name='publication_status'"
        ) == 1

        # Migration 003 must not create version tables until 002 is recorded.
        await expect_migration_failure(migration_003)
        assert await conn.fetchval("SELECT to_regclass('public.idea_versions')") is None
        markers = await conn.fetch("SELECT version FROM app_schema_migrations ORDER BY version")
        assert [row["version"] for row in markers] == ["001_idea_visibility_and_acl"]

        # Migration 004 must not run before the complete prior schema exists.
        await expect_migration_failure(migration_004)
        assert await conn.fetchval("SELECT to_regclass('public.collaborations')") is None

        # Migrations 005–013 must wait for their prerequisite schema.
        await expect_migration_failure(migration_005)
        await expect_migration_failure(migration_006)
        await expect_migration_failure(migration_007)
        await expect_migration_failure(migration_008)
        await expect_migration_failure(migration_009)
        await expect_migration_failure(migration_010)
        await expect_migration_failure(migration_011)
        await expect_migration_failure(migration_012)
        await expect_migration_failure(migration_013)
        assert await conn.fetchval("SELECT COUNT(*) FROM information_schema.columns WHERE table_schema='public' AND table_name='idea_contributions' AND column_name='source_collaboration_contribution_id'") == 0
        assert await conn.fetchval("SELECT to_regclass('public.idea_associations')") is None
        assert await conn.fetchval("SELECT to_regclass('public.notification_preferences')") is None

        # After the prerequisite is applied, the remaining migrations succeed.
        await conn.execute(migration_002)
        await conn.execute(migration_003)
        await conn.execute(migration_004)
        await conn.execute(migration_005)
        await conn.execute(migration_006)
        await conn.execute(migration_007)
        await conn.execute(migration_008)
        await conn.execute(migration_009)
        await conn.execute(migration_010)
        await conn.execute(migration_011)
        await conn.execute(migration_012)
        await conn.execute(migration_013)
        assert await conn.fetchval(
            "SELECT character_maximum_length FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name='notifications' AND column_name='type'"
        ) == 40
        markers = await conn.fetch("SELECT version FROM app_schema_migrations ORDER BY version")
        assert {row["version"] for row in markers} == {
            "001_idea_visibility_and_acl",
            "002_idea_contributions",
            "003_idea_versions_and_attribution",
            "004_collaborations",
            "005_collaboration_attribution",
            "006_idea_associations",
            "007_notification_preferences",
            "008_collaboration_member_leave",
            "009_collaboration_notification_links",
            "010_idea_reports",
            "011_user_follows",
            "012_legacy_license_deadlines",
            "013_notification_type_length",
        }
        owner_id, contributor_id = uuid.uuid4(), uuid.uuid4()
        await conn.executemany(
            "INSERT INTO users(id) VALUES($1)",
            [(owner_id,), (contributor_id,)],
        )
        collab_id = uuid.uuid4()
        await conn.execute(
            "INSERT INTO collaborations(id, title, owner_id) VALUES($1, $2, $3)",
            collab_id, "member leave state", owner_id,
        )
        await conn.execute(
            "INSERT INTO collaboration_members(collaboration_id, user_id, role, status, invited_by) "
            "VALUES($1, $2, 'contributor', 'left', $3)",
            collab_id, contributor_id, owner_id,
        )
        assert await conn.fetchval(
            "SELECT status FROM collaboration_members WHERE collaboration_id=$1 AND user_id=$2",
            collab_id, contributor_id,
        ) == "left"
        notification_id = uuid.uuid4()
        await conn.execute(
            "INSERT INTO notifications(id, user_id, type, content, collaboration_id) "
            "VALUES($1, $2, 'collab_invited', 'workspace invite', $3)",
            notification_id, contributor_id, collab_id,
        )
        assert await conn.fetchval(
            "SELECT collaboration_id FROM notifications WHERE id=$1", notification_id
        ) == collab_id
        await conn.execute(
            "INSERT INTO user_follows(follower_id, following_id) VALUES($1, $2)",
            contributor_id, owner_id,
        )
        assert await conn.fetchval(
            "SELECT COUNT(*) FROM user_follows WHERE follower_id=$1 AND following_id=$2",
            contributor_id, owner_id,
        ) == 1
    finally:
        # Ensure cleanup can run even if an unexpected SQL assertion left the
        # connection inside an aborted transaction.
        try:
            await conn.execute("ROLLBACK")
        except asyncpg.PostgresError:
            pass
        await conn.execute("""
            DROP TABLE IF EXISTS user_follows CASCADE;
            DROP TABLE IF EXISTS idea_reports CASCADE;
            DROP TABLE IF EXISTS notification_preferences CASCADE;
            DROP TABLE IF EXISTS idea_associations CASCADE;
            DROP TABLE IF EXISTS collaboration_events CASCADE;
            DROP TABLE IF EXISTS collaboration_contributions CASCADE;
            DROP TABLE IF EXISTS collaboration_sources CASCADE;
            DROP TABLE IF EXISTS collaboration_members CASCADE;
            DROP TABLE IF EXISTS collaborations CASCADE;
            DROP TABLE IF EXISTS idea_version_contributions CASCADE;
            DROP TABLE IF EXISTS idea_versions CASCADE;
            DROP TABLE IF EXISTS idea_contributions CASCADE;
            DROP TABLE IF EXISTS idea_access_grants CASCADE;
            DROP TABLE IF EXISTS app_schema_migrations CASCADE;
            DROP TABLE IF EXISTS fork_relations CASCADE;
            DROP TABLE IF EXISTS ideas CASCADE;
            DROP TABLE IF EXISTS users CASCADE;
        """)
        await conn.close()
