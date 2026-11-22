-- IDEAS V2.0 / Migration 005: preserve workspace proposal attribution in Idea versions
-- PostgreSQL 16+. MANUAL / REVIEW REQUIRED. Requires migrations 001..004.

BEGIN;

DO $migration$
BEGIN
  IF to_regclass('public.app_schema_migrations') IS NULL
     OR NOT EXISTS (SELECT 1 FROM app_schema_migrations WHERE version = '001_idea_visibility_and_acl')
     OR NOT EXISTS (SELECT 1 FROM app_schema_migrations WHERE version = '002_idea_contributions')
     OR NOT EXISTS (SELECT 1 FROM app_schema_migrations WHERE version = '003_idea_versions_and_attribution')
     OR NOT EXISTS (SELECT 1 FROM app_schema_migrations WHERE version = '004_collaborations') THEN
    RAISE EXCEPTION 'Migrations 001..004 must be applied before 005';
  END IF;
END;
$migration$;

ALTER TABLE idea_contributions
  ADD COLUMN source_collaboration_contribution_id UUID
  REFERENCES collaboration_contributions(id) ON DELETE RESTRICT;

CREATE UNIQUE INDEX uq_idea_contribution_collaboration_source
  ON idea_contributions(source_collaboration_contribution_id)
  WHERE source_collaboration_contribution_id IS NOT NULL;

INSERT INTO app_schema_migrations(version) VALUES ('005_collaboration_attribution');

COMMIT;
