-- IDEAS V2.0 / Migration 011: creator follows
-- PostgreSQL 16+. Requires migration 001 and current moderation schema 010.

BEGIN;

DO $migration$
BEGIN
  IF to_regclass('public.app_schema_migrations') IS NULL
     OR NOT EXISTS (SELECT 1 FROM app_schema_migrations WHERE version = '001_idea_visibility_and_acl')
     OR NOT EXISTS (SELECT 1 FROM app_schema_migrations WHERE version = '010_idea_reports') THEN
    RAISE EXCEPTION 'Migrations 001 and 010 must be applied before 011';
  END IF;
  IF EXISTS (SELECT 1 FROM app_schema_migrations WHERE version = '011_user_follows') THEN
    RAISE EXCEPTION 'Migration 011 has already been applied';
  END IF;
END;
$migration$;

CREATE TABLE user_follows (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  follower_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  following_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_user_follow_pair UNIQUE(follower_id, following_id),
  CONSTRAINT ck_user_follow_no_self CHECK (follower_id <> following_id)
);
CREATE INDEX idx_user_follows_following_created ON user_follows(following_id, created_at DESC);
CREATE INDEX idx_user_follows_follower_created ON user_follows(follower_id, created_at DESC);

INSERT INTO app_schema_migrations(version) VALUES ('011_user_follows');

COMMIT;
