-- IDEAS V2.0 / Migration 008: explicit collaboration member departure state
-- PostgreSQL 16+. MANUAL / REVIEW REQUIRED. Requires migrations 004 and 007.

BEGIN;

DO $migration$
BEGIN
  IF to_regclass('public.app_schema_migrations') IS NULL
     OR NOT EXISTS (SELECT 1 FROM app_schema_migrations WHERE version = '004_collaborations')
     OR NOT EXISTS (SELECT 1 FROM app_schema_migrations WHERE version = '007_notification_preferences') THEN
    RAISE EXCEPTION 'Migrations 004 and 007 must be applied before 008';
  END IF;
  IF EXISTS (SELECT 1 FROM app_schema_migrations WHERE version = '008_collaboration_member_leave') THEN
    RAISE EXCEPTION 'Migration 008 has already been applied';
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
VALUES ('008_collaboration_member_leave');

COMMIT;
