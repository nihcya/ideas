-- IDEAS V2.0 / Migration 004: first-class asynchronous collaboration workspaces
-- PostgreSQL 16+. MANUAL / REVIEW REQUIRED. Requires migrations 001, 002 and 003.
-- Existing per-Idea invitations/contributions remain supported for compatibility.

BEGIN;

DO $migration$
BEGIN
  IF to_regclass('public.app_schema_migrations') IS NULL
     OR NOT EXISTS (SELECT 1 FROM app_schema_migrations WHERE version = '001_idea_visibility_and_acl')
     OR NOT EXISTS (SELECT 1 FROM app_schema_migrations WHERE version = '002_idea_contributions')
     OR NOT EXISTS (SELECT 1 FROM app_schema_migrations WHERE version = '003_idea_versions_and_attribution') THEN
    RAISE EXCEPTION 'Migrations 001, 002 and 003 must be applied before 004';
  END IF;
END;
$migration$;

CREATE TABLE collaborations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title VARCHAR(120) NOT NULL,
  description TEXT,
  owner_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  status VARCHAR(16) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','published','archived')),
  visibility VARCHAR(16) NOT NULL DEFAULT 'private' CHECK (visibility IN ('private','public')),
  published_idea_id UUID REFERENCES ideas(id) ON DELETE SET NULL,
  published_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_collaborations_owner ON collaborations(owner_id);

CREATE TABLE collaboration_members (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  collaboration_id UUID NOT NULL REFERENCES collaborations(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role VARCHAR(16) NOT NULL CHECK (role IN ('owner','contributor','viewer')),
  status VARCHAR(16) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','accepted','declined','revoked')),
  invited_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  invited_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  responded_at TIMESTAMPTZ,
  revoked_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_collaboration_member_user UNIQUE(collaboration_id, user_id)
);
CREATE INDEX idx_collaboration_members_user_status ON collaboration_members(user_id, status);

CREATE TABLE collaboration_sources (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  collaboration_id UUID NOT NULL REFERENCES collaborations(id) ON DELETE CASCADE,
  idea_id UUID NOT NULL REFERENCES ideas(id) ON DELETE RESTRICT,
  position INTEGER NOT NULL DEFAULT 0,
  rights_snapshot JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_collaboration_source_idea UNIQUE(collaboration_id, idea_id)
);
CREATE INDEX idx_collaboration_sources_collaboration ON collaboration_sources(collaboration_id, position);

CREATE TABLE collaboration_contributions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  collaboration_id UUID NOT NULL REFERENCES collaborations(id) ON DELETE CASCADE,
  author_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  source_idea_id UUID REFERENCES ideas(id) ON DELETE SET NULL,
  contribution_type VARCHAR(16) NOT NULL DEFAULT 'idea' CHECK (contribution_type IN ('idea','revision','comment','research')),
  content TEXT NOT NULL,
  note TEXT,
  status VARCHAR(16) NOT NULL DEFAULT 'submitted' CHECK (status IN ('submitted','accepted','rejected','withdrawn')),
  reviewed_by UUID REFERENCES users(id) ON DELETE SET NULL,
  reviewed_at TIMESTAMPTZ,
  review_note TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_collab_contributions_workspace_status ON collaboration_contributions(collaboration_id, status, created_at);
CREATE INDEX idx_collab_contributions_author ON collaboration_contributions(author_id, status);

CREATE TABLE collaboration_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  collaboration_id UUID NOT NULL REFERENCES collaborations(id) ON DELETE CASCADE,
  actor_id UUID REFERENCES users(id) ON DELETE SET NULL,
  event_type VARCHAR(40) NOT NULL,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_collaboration_events_timeline ON collaboration_events(collaboration_id, created_at);

INSERT INTO app_schema_migrations(version) VALUES ('004_collaborations');

COMMIT;
