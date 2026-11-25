-- IDEAS V2.0 / Migration 010: user reports and moderation workflow
-- PostgreSQL 16+. Requires migrations 001 and 009.

BEGIN;

DO $migration$
BEGIN
  IF to_regclass('public.app_schema_migrations') IS NULL
     OR NOT EXISTS (SELECT 1 FROM app_schema_migrations WHERE version = '001_idea_visibility_and_acl')
     OR NOT EXISTS (SELECT 1 FROM app_schema_migrations WHERE version = '009_collaboration_notification_links') THEN
    RAISE EXCEPTION 'Migrations 001 and 009 must be applied before 010';
  END IF;
  IF EXISTS (SELECT 1 FROM app_schema_migrations WHERE version = '010_idea_reports') THEN
    RAISE EXCEPTION 'Migration 010 has already been applied';
  END IF;
END;
$migration$;

CREATE TABLE idea_reports (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  idea_id UUID NOT NULL REFERENCES ideas(id) ON DELETE CASCADE,
  reporter_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  reason VARCHAR(24) NOT NULL CHECK (reason IN ('spam','harassment','copyright','privacy','misinformation','other')),
  description TEXT,
  status VARCHAR(16) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','in_review','resolved','dismissed')),
  reviewed_by UUID REFERENCES users(id) ON DELETE SET NULL,
  reviewed_at TIMESTAMPTZ,
  resolution_note VARCHAR(2000),
  action_taken VARCHAR(24) NOT NULL DEFAULT 'none',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_idea_reports_status_created ON idea_reports(status, created_at);
CREATE INDEX idx_idea_reports_idea_status ON idea_reports(idea_id, status);

INSERT INTO app_schema_migrations(version) VALUES ('010_idea_reports');

COMMIT;
