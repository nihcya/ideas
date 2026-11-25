"""Existing SQLite databases receive the new collaboration attribution column safely."""
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from database import _migrate_sqlite_columns


@pytest.mark.asyncio
async def test_existing_sqlite_schema_adds_collaboration_attribution_column_and_unique_index():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with test_engine.begin() as conn:
            statements = [
                "CREATE TABLE users (id CHAR(32) PRIMARY KEY, username VARCHAR(20) NOT NULL)",
                "CREATE TABLE ideas (id CHAR(32) PRIMARY KEY, status VARCHAR(16) NOT NULL, created_at DATETIME NOT NULL, is_forkable BOOLEAN NOT NULL DEFAULT 0)",
                "CREATE TABLE fork_relations (id CHAR(32) PRIMARY KEY)",
                "CREATE TABLE idea_contributions (id CHAR(32) PRIMARY KEY, idea_id CHAR(32) NOT NULL, author_id CHAR(32) NOT NULL, content TEXT NOT NULL)",
                "INSERT INTO ideas(id, status, created_at, is_forkable) VALUES ('00000000000000000000000000000001', 'active', CURRENT_TIMESTAMP, 1)",
            ]
            for statement in statements:
                await conn.execute(text(statement))

        await _migrate_sqlite_columns(test_engine)

        async with test_engine.connect() as conn:
            columns = await conn.execute(text("PRAGMA table_info(idea_contributions)"))
            names = {row[1] for row in columns.fetchall()}
            assert "source_collaboration_contribution_id" in names

            indexes = await conn.execute(text("PRAGMA index_list(idea_contributions)"))
            index_names = {row[1] for row in indexes.fetchall()}
            assert "uq_idea_contribution_collaboration_source" in index_names

            marker = await conn.execute(text(
                "SELECT version FROM app_schema_migrations "
                "WHERE version = '001_idea_visibility_and_acl'"
            ))
            assert marker.scalar_one() == "001_idea_visibility_and_acl"

            idea = await conn.execute(text(
                "SELECT publication_status, visibility, legacy_license_review_status "
                "FROM ideas WHERE id = '00000000000000000000000000000001'"
            ))
            assert tuple(idea.one()) == ("published", "public", "pending")
    finally:
        await test_engine.dispose()
