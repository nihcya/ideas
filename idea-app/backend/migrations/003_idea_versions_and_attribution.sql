-- IDEAS V2.0 / Migration 003: author-controlled version drafts and attribution
-- PostgreSQL 16+. MANUAL / REVIEW REQUIRED. Requires migrations 001 and 002.
-- No historical versions are fabricated: existing Ideas receive their first version
-- only when the author creates a new draft. A contribution can be consumed once.

BEGIN;

DO $
BEGIN
  IF to_regclass('public.app_schema_migrations') IS NULL THEN
    RAISE EXCEPTION 'Migrations 001 and 002 must be applied first';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM app_schema_migrations
    WHERE version = '001_idea_visibility_and_acl'
  ) OR NOT EXISTS (
    SELECT 1 FROM app_schema_migrations
    WHERE version = '002_idea_contributions'
  ) THEN
    RAISE EXCEPTION 'Migrations 001 and 002 must be applied first';
  END IF;
END;
$;

CREATE TABLE IF NOT EXISTS idea_versions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  idea_id UUID NOT NULL REFERENCES ideas(id) ON DELETE CASCADE,
  version_number INTEGER NOT NULL CHECK (version_number > 0),
  content_snapshot VARCHAR(300) NOT NULL,
  change_summary TEXT,
  status VARCHAR(16) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','published')),
  created_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  published_by UUID REFERENCES users(id) ON DELETE SET NULL,
  published_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_idea_versions_number UNIQUE (idea_id, version_number)
);

CREATE INDEX IF NOT EXISTS idx_idea_versions_idea_status_number
  ON idea_versions (idea_id, status, version_number);

CREATE TABLE IF NOT EXISTS idea_version_contributions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  version_id UUID NOT NULL REFERENCES idea_versions(id) ON DELETE CASCADE,
  contribution_id UUID NOT NULL REFERENCES idea_contributions(id) ON DELETE RESTRICT,
  author_id_snapshot UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  author_name_snapshot VARCHAR(80) NOT NULL,
  content_snapshot TEXT NOT NULL,
  CONSTRAINT uq_version_contribution_consumed_once UNIQUE (contribution_id),
  CONSTRAINT uq_version_contribution_pair UNIQUE (version_id, contribution_id)
);

CREATE INDEX IF NOT EXISTS idx_idea_version_contributions_version
  ON idea_version_contributions (version_id);

INSERT INTO app_schema_migrations(version)
VALUES ('003_idea_versions_and_attribution')
ON CONFLICT (version) DO NOTHING;

COMMIT;

-- Validation:
-- SELECT status, COUNT(*) FROM idea_versions GROUP BY status;
-- SELECT COUNT(*) FROM idea_version_contributions;
-- Verify unique constraints and indexes before enabling version endpoints.
