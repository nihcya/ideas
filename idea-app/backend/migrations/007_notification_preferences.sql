-- IDEAS V2.0 / Migration 007: per-user notification preferences
-- PostgreSQL 16+. Requires migrations 001..006.

BEGIN;

DO $migration$
BEGIN
  IF to_regclass('public.app_schema_migrations') IS NULL
     OR NOT EXISTS (SELECT 1 FROM app_schema_migrations WHERE version = '001_idea_visibility_and_acl')
     OR NOT EXISTS (SELECT 1 FROM app_schema_migrations WHERE version = '002_idea_contributions')
     OR NOT EXISTS (SELECT 1 FROM app_schema_migrations WHERE version = '003_idea_versions_and_attribution')
     OR NOT EXISTS (SELECT 1 FROM app_schema_migrations WHERE version = '004_collaborations')
     OR NOT EXISTS (SELECT 1 FROM app_schema_migrations WHERE version = '005_collaboration_attribution')
     OR NOT EXISTS (SELECT 1 FROM app_schema_migrations WHERE version = '006_idea_associations') THEN
    RAISE EXCEPTION 'Migrations 001..006 must be applied before 007';
  END IF;
END;
$migration$;

CREATE TABLE notification_preferences (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  notification_type VARCHAR(32) NOT NULL,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_notification_preference_user_type UNIQUE(user_id, notification_type)
);
CREATE INDEX idx_notification_preferences_user ON notification_preferences(user_id);

INSERT INTO app_schema_migrations(version) VALUES ('007_notification_preferences');

COMMIT;
