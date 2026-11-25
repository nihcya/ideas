"""Static contract checks for the manually-applied PostgreSQL migrations.

These checks catch obvious migration drift and malformed PL/pgSQL wrappers. They do
not execute SQL and are not a substitute for PostgreSQL integration tests.
"""
from pathlib import Path
import re


MIGRATIONS = Path(__file__).resolve().parent.parent / "migrations"


def _read(name: str) -> str:
    return (MIGRATIONS / name).read_text(encoding="utf-8")


def _assert_transaction_wrapped(sql: str) -> None:
    assert re.search(r"(?im)^BEGIN;\s*$", sql)
    assert re.search(r"(?im)^COMMIT;\s*$", sql)


def test_migration_001_has_valid_dollar_quoted_guard_and_acl_schema():
    sql = _read("001_idea_visibility_and_acl.sql")
    _assert_transaction_wrapped(sql)

    assert re.search(
        r"(?is)DO \$migration\$\s*BEGIN.*?END;\s*\$migration\$;",
        sql,
    ), "Migration 001 must use a syntactically complete DO $$ ... END; $$; block"
    assert "DO $\n" not in sql
    assert "CREATE TABLE IF NOT EXISTS idea_access_grants" in sql
    assert "UNIQUE (idea_id, user_id)" in sql
    assert "INSERT INTO app_schema_migrations(version) VALUES ('001_idea_visibility_and_acl')" in sql


def test_migration_002_requires_migration_001_and_matches_contribution_states():
    sql = _read("002_idea_contributions.sql")
    _assert_transaction_wrapped(sql)

    assert "Migration 001_idea_visibility_and_acl must be applied first" in sql
    assert "to_regclass('public.app_schema_migrations')" in sql
    for state in ("submitted", "accepted", "rejected", "withdrawn"):
        assert f"'{state}'" in sql
    assert "REFERENCES ideas(id) ON DELETE CASCADE" in sql
    assert "REFERENCES users(id) ON DELETE CASCADE" in sql


def test_migration_003_requires_001_and_002_and_enforces_single_attribution():
    sql = _read("003_idea_versions_and_attribution.sql")
    _assert_transaction_wrapped(sql)

    assert "Migrations 001 and 002 must be applied first" in sql
    assert "UNIQUE (idea_id, version_number)" in sql
    assert "UNIQUE (contribution_id)" in sql
    assert "UNIQUE (version_id, contribution_id)" in sql
    assert "REFERENCES idea_contributions(id) ON DELETE RESTRICT" in sql
    assert "REFERENCES idea_versions(id) ON DELETE CASCADE" in sql

def test_migration_014_enforces_one_open_report_per_reporter_and_idea():
    sql = _read("014_idea_report_open_uniqueness.sql")
    _assert_transaction_wrapped(sql)

    assert "Migration 010_idea_reports must be applied before 014" in sql
    assert "CREATE UNIQUE INDEX uq_idea_reports_open_per_reporter" in sql
    assert "ON idea_reports(idea_id, reporter_id)" in sql
    assert "WHERE status IN ('pending', 'in_review')" in sql
    assert "014_idea_report_open_uniqueness" in sql
