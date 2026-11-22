-- IDEAS V2.0 / Migration 007: explicit collaboration member departure state
-- PostgreSQL 16+. MANUAL / REVIEW REQUIRED. Requires migration 004.

BEGIN;

DO $migration$
BEGIN
  IF to_regclass('public.app_schema_migrations') IS NULL
     OR NOT EXISTS (SELECT 1 FROM app_schema_migrations WHERE version = '004_collaborations') THEN
    RAISE EXCEPTION 'Migration 004 must be applied before 007';
  END IF;
  IF EXISTS (SELECT 1 FROM app_schema_migrations WHERE version = '007_collaboration_member_leave') THEN
    RAISE EXCEPTION 'Migration 007 has already been applied';
  END IF;
END;
$migration$;

ALTER TABLE collaboration_members
  DROP CONSTRAINT IF EXISTS collaboration_members_status_check;

ALTER TABLE collaboration_members
  DROP CONSTRAINT IF EXISTS ck_collaboration_member_status;

ALTER TABLE collaboration_members
  ADD CONSTRAINT ck_collaboration_member_status
  CHECK (status IN ('pending','accepted','declined','revoked','left'));

INSERT INTO app_schema_migrations(version)
VALUES ('007_collaboration_member_leave');

COMMIT;
