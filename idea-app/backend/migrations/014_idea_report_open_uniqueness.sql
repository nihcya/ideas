-- IDEAS V2.0 / Migration 014: prevent concurrent duplicate open reports
-- PostgreSQL 16+. Requires migration 010.

BEGIN;

DO $migration$
BEGIN
  IF to_regclass('public.app_schema_migrations') IS NULL
     OR NOT EXISTS (
       SELECT 1 FROM app_schema_migrations
       WHERE version = '010_idea_reports'
     ) THEN
    RAISE EXCEPTION 'Migration 010_idea_reports must be applied before 014';
  END IF;
  IF EXISTS (
    SELECT 1 FROM app_schema_migrations
    WHERE version = '014_idea_report_open_uniqueness'
  ) THEN
    RAISE EXCEPTION 'Migration 014 has already been applied';
  END IF;
END;
$migration$;

-- Existing duplicate open reports must be reviewed before applying this index.
-- The index intentionally fails rather than silently discarding user reports.
CREATE UNIQUE INDEX uq_idea_reports_open_per_reporter
  ON idea_reports(idea_id, reporter_id)
  WHERE status IN ('pending', 'in_review');

INSERT INTO app_schema_migrations(version)
VALUES ('014_idea_report_open_uniqueness');

COMMIT;
