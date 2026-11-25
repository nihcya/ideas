-- IDEAS V2.0 / Migration 013: support extended notification event identifiers
-- PostgreSQL 16+. Requires migration 012.

BEGIN;

DO $migration$
BEGIN
  IF to_regclass('public.app_schema_migrations') IS NULL
     OR NOT EXISTS (SELECT 1 FROM app_schema_migrations WHERE version = '012_legacy_license_deadlines') THEN
    RAISE EXCEPTION 'Migration 012 must be applied before 013';
  END IF;
  IF EXISTS (SELECT 1 FROM app_schema_migrations WHERE version = '013_notification_type_length') THEN
    RAISE EXCEPTION 'Migration 013 has already been applied';
  END IF;
END;
$migration$;

ALTER TABLE notifications
  ALTER COLUMN type TYPE VARCHAR(40);

INSERT INTO app_schema_migrations(version) VALUES ('013_notification_type_length');

COMMIT;
