-- IDEAS V2.0 / Migration 012: enforce 90-day legacy authorization transition
-- PostgreSQL 16+. Requires migration 001 and current V2 schema 011.

BEGIN;

DO $migration$
BEGIN
  IF to_regclass('public.app_schema_migrations') IS NULL
     OR NOT EXISTS (SELECT 1 FROM app_schema_migrations WHERE version = '001_idea_visibility_and_acl')
     OR NOT EXISTS (SELECT 1 FROM app_schema_migrations WHERE version = '011_user_follows') THEN
    RAISE EXCEPTION 'Migrations 001 and 011 must be applied before 012';
  END IF;
  IF EXISTS (SELECT 1 FROM app_schema_migrations WHERE version = '012_legacy_license_deadlines') THEN
    RAISE EXCEPTION 'Migration 012 has already been applied';
  END IF;
END;
$migration$;

ALTER TABLE ideas
  ADD COLUMN legacy_license_review_due_at TIMESTAMPTZ;

-- The 90-day window starts at V2.0 activation (Migration 001 application time),
-- not at each Idea's historical creation date.
UPDATE ideas
SET legacy_license_review_due_at = (
  SELECT applied_at FROM app_schema_migrations
  WHERE version = '001_idea_visibility_and_acl'
) + INTERVAL '90 days'
WHERE legacy_license_review_status = 'pending';

CREATE INDEX idx_ideas_legacy_license_due
  ON ideas(legacy_license_review_status, legacy_license_review_due_at)
  WHERE legacy_license_review_status = 'pending';

INSERT INTO app_schema_migrations(version) VALUES ('012_legacy_license_deadlines');

COMMIT;
