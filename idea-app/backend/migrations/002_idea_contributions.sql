-- IDEAS V2.0 / Migration 002: asynchronous Idea contributions
-- PostgreSQL 16+. MANUAL / REVIEW REQUIRED.
-- Requires migration 001 (ideas and idea_access_grants).
-- Back up production before applying. This migration is not run at startup.

BEGIN;

DO $
BEGIN
  IF to_regclass('public.app_schema_migrations') IS NULL THEN
    RAISE EXCEPTION 'Migration 001_idea_visibility_and_acl must be applied first';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM app_schema_migrations
    WHERE version = '001_idea_visibility_and_acl'
  ) THEN
    RAISE EXCEPTION 'Migration 001_idea_visibility_and_acl must be applied first';
  END IF;
END;
$;

CREATE TABLE IF NOT EXISTS idea_contributions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  idea_id UUID NOT NULL REFERENCES ideas(id) ON DELETE CASCADE,
  author_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  content TEXT NOT NULL,
  note TEXT,
  status VARCHAR(16) NOT NULL DEFAULT 'submitted'
    CHECK (status IN ('submitted','accepted','rejected','withdrawn')),
  reviewed_by UUID REFERENCES users(id) ON DELETE SET NULL,
  reviewed_at TIMESTAMPTZ,
  review_note TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_idea_contributions_idea_status_created
  ON idea_contributions (idea_id, status, created_at);
CREATE INDEX IF NOT EXISTS idx_idea_contributions_author_status
  ON idea_contributions (author_id, status);

INSERT INTO app_schema_migrations(version)
VALUES ('002_idea_contributions')
ON CONFLICT (version) DO NOTHING;

COMMIT;

-- Post-migration validation:
-- SELECT status, COUNT(*) FROM idea_contributions GROUP BY status;
-- Verify FK constraints and both indexes before enabling contribution endpoints.
