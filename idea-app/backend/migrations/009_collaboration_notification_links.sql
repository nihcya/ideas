-- IDEAS V2.0 / Migration 009: collaboration notification deep links
-- PostgreSQL 16+. Requires migrations 004 and 008.

BEGIN;

DO $migration$
BEGIN
  IF to_regclass('public.app_schema_migrations') IS NULL
     OR NOT EXISTS (SELECT 1 FROM app_schema_migrations WHERE version = '004_collaborations')
     OR NOT EXISTS (SELECT 1 FROM app_schema_migrations WHERE version = '008_collaboration_member_leave') THEN
    RAISE EXCEPTION 'Migrations 004 and 008 must be applied before 009';
  END IF;
  IF EXISTS (SELECT 1 FROM app_schema_migrations WHERE version = '009_collaboration_notification_links') THEN
    RAISE EXCEPTION 'Migration 009 has already been applied';
  END IF;
  IF to_regclass('public.notifications') IS NULL THEN
    RAISE EXCEPTION 'notifications table must exist before migration 009';
  END IF;
END;
$migration$;

ALTER TABLE notifications
  ADD COLUMN collaboration_id UUID REFERENCES collaborations(id) ON DELETE SET NULL;

CREATE INDEX idx_notifications_collaboration_id
  ON notifications(collaboration_id)
  WHERE collaboration_id IS NOT NULL;

INSERT INTO app_schema_migrations(version)
VALUES ('009_collaboration_notification_links');

COMMIT;
