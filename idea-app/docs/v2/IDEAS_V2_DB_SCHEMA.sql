-- IDEAS V2.0 additive migration draft
-- Target: PostgreSQL 16+. Review against deployed schema and rehearse on a backup first.
-- This is an additive proposal; it does not drop legacy tables or rewrite historical content.
-- SQLite fallback needs a separately tested migration.

BEGIN;

-- 1. Publication state is separate from existing lifecycle/moderation status.
ALTER TABLE ideas
  ADD COLUMN IF NOT EXISTS publication_status VARCHAR(16) NOT NULL DEFAULT 'draft',
  ADD COLUMN IF NOT EXISTS visibility VARCHAR(16) NOT NULL DEFAULT 'private',
  ADD COLUMN IF NOT EXISTS license_code VARCHAR(32) NOT NULL DEFAULT 'legacy_unspecified',
  ADD COLUMN IF NOT EXISTS license_text_snapshot TEXT,
  ADD COLUMN IF NOT EXISTS license_version INTEGER NOT NULL DEFAULT 1,
  ADD COLUMN IF NOT EXISTS published_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS allow_fork BOOLEAN NOT NULL DEFAULT FALSE;

-- Conservative backfill: do not silently make historical content public or grant rights.
UPDATE ideas SET publication_status='draft', visibility='private',
  license_code='legacy_unspecified', allow_fork=FALSE
WHERE publication_status IS NULL OR visibility IS NULL;

ALTER TABLE ideas ADD CONSTRAINT ck_ideas_publication_status
  CHECK (publication_status IN ('draft','published','archived')) NOT VALID;
ALTER TABLE ideas ADD CONSTRAINT ck_ideas_visibility
  CHECK (visibility IN ('private','public')) NOT VALID;
ALTER TABLE ideas ADD CONSTRAINT ck_ideas_license_code
  CHECK (license_code IN ('all_rights_reserved','attribution','attribution_adaptation','custom','legacy_unspecified')) NOT VALID;
ALTER TABLE ideas ADD CONSTRAINT ck_ideas_license_version
  CHECK (license_version >= 1) NOT VALID;
ALTER TABLE ideas VALIDATE CONSTRAINT ck_ideas_publication_status;
ALTER TABLE ideas VALIDATE CONSTRAINT ck_ideas_visibility;
ALTER TABLE ideas VALIDATE CONSTRAINT ck_ideas_license_code;
ALTER TABLE ideas VALIDATE CONSTRAINT ck_ideas_license_version;

CREATE INDEX IF NOT EXISTS idx_ideas_public_explore
  ON ideas (published_at DESC, created_at DESC)
  WHERE publication_status='published' AND visibility='public' AND status='active';
CREATE INDEX IF NOT EXISTS idx_ideas_author_publication
  ON ideas (author_id, publication_status, visibility);

-- 2. Extend existing fork_relations rather than creating a duplicate graph table.
ALTER TABLE fork_relations
  ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS created_by UUID REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE fork_relations DROP CONSTRAINT IF EXISTS ck_fork_relation_type;
ALTER TABLE fork_relations ADD CONSTRAINT ck_fork_relation_type
  CHECK (relation_type IN ('fork','merge','evolve','inspired')) NOT VALID;
ALTER TABLE fork_relations VALIDATE CONSTRAINT ck_fork_relation_type;
ALTER TABLE fork_relations ADD CONSTRAINT ck_fork_relation_no_self
  CHECK (child_id <> parent_id) NOT VALID;
ALTER TABLE fork_relations VALIDATE CONSTRAINT ck_fork_relation_no_self;
CREATE UNIQUE INDEX IF NOT EXISTS uq_fork_relation_edge_type
  ON fork_relations (child_id, parent_id, relation_type);

-- NOTE: CHECK cannot prevent multi-row cycles. The relation service must perform a
-- recursive reachability check in a transaction with deterministic locking.

-- 3. Version history.
CREATE TABLE IF NOT EXISTS idea_versions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  idea_id UUID NOT NULL REFERENCES ideas(id) ON DELETE CASCADE,
  version_number INTEGER NOT NULL CHECK (version_number >= 1),
  content_snapshot VARCHAR(300) NOT NULL,
  editor_id UUID REFERENCES users(id) ON DELETE SET NULL,
  change_source VARCHAR(24) NOT NULL DEFAULT 'user'
    CHECK (change_source IN ('user','ai_assisted','collaboration','migration')),
  ai_assisted BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (idea_id, version_number)
);
CREATE INDEX IF NOT EXISTS idx_idea_versions_idea_created ON idea_versions (idea_id, created_at DESC);

-- 4. Asynchronous collaboration.
CREATE TABLE IF NOT EXISTS idea_collaborations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title VARCHAR(120) NOT NULL,
  description TEXT,
  status VARCHAR(16) NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft','open','reviewing','published','cancelled')),
  visibility VARCHAR(16) NOT NULL DEFAULT 'private' CHECK (visibility IN ('private','public')),
  published_idea_id UUID REFERENCES ideas(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  closed_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_collaborations_owner_updated ON idea_collaborations (owner_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS collaboration_members (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  collaboration_id UUID NOT NULL REFERENCES idea_collaborations(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role VARCHAR(16) NOT NULL CHECK (role IN ('owner','contributor','viewer')),
  invite_status VARCHAR(16) NOT NULL DEFAULT 'pending'
    CHECK (invite_status IN ('pending','accepted','declined','revoked')),
  invited_by UUID REFERENCES users(id) ON DELETE SET NULL,
  invited_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  responded_at TIMESTAMPTZ,
  UNIQUE (collaboration_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_collab_members_user_status ON collaboration_members (user_id, invite_status);

CREATE TABLE IF NOT EXISTS collaboration_source_ideas (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  collaboration_id UUID NOT NULL REFERENCES idea_collaborations(id) ON DELETE CASCADE,
  idea_id UUID NOT NULL REFERENCES ideas(id) ON DELETE RESTRICT,
  relation_type VARCHAR(16) NOT NULL DEFAULT 'merge'
    CHECK (relation_type IN ('fork','merge','evolve','inspired')),
  license_code_snapshot VARCHAR(32) NOT NULL,
  license_text_snapshot TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (collaboration_id, idea_id)
);
CREATE INDEX IF NOT EXISTS idx_collab_source_idea ON collaboration_source_ideas (idea_id);

-- 5. Contribution and attribution records.
CREATE TABLE IF NOT EXISTS idea_contributions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  collaboration_id UUID NOT NULL REFERENCES idea_collaborations(id) ON DELETE CASCADE,
  contributor_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  contribution_type VARCHAR(20) NOT NULL DEFAULT 'idea'
    CHECK (contribution_type IN ('idea','revision','comment','research')),
  content TEXT NOT NULL,
  source_idea_id UUID REFERENCES ideas(id) ON DELETE SET NULL,
  ai_assisted BOOLEAN NOT NULL DEFAULT FALSE,
  status VARCHAR(16) NOT NULL DEFAULT 'submitted'
    CHECK (status IN ('draft','submitted','accepted','rejected','withdrawn')),
  submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  reviewed_by UUID REFERENCES users(id) ON DELETE SET NULL,
  reviewed_at TIMESTAMPTZ,
  review_note TEXT
);
CREATE INDEX IF NOT EXISTS idx_contributions_collab_status ON idea_contributions (collaboration_id, status, submitted_at);
CREATE INDEX IF NOT EXISTS idx_contributions_author ON idea_contributions (contributor_id, submitted_at DESC);

CREATE TABLE IF NOT EXISTS idea_contributors (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  idea_id UUID NOT NULL REFERENCES ideas(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  role VARCHAR(20) NOT NULL DEFAULT 'contributor' CHECK (role IN ('author','contributor')),
  contribution_count INTEGER NOT NULL DEFAULT 1 CHECK (contribution_count >= 0),
  attribution_note TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (idea_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_idea_contributors_user ON idea_contributors (user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS collaboration_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  collaboration_id UUID NOT NULL REFERENCES idea_collaborations(id) ON DELETE CASCADE,
  actor_id UUID REFERENCES users(id) ON DELETE SET NULL,
  event_type VARCHAR(32) NOT NULL,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_collab_events_timeline ON collaboration_events (collaboration_id, created_at);

-- 6. Idempotency records for create/publish actions.
CREATE TABLE IF NOT EXISTS idempotency_records (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  idempotency_key VARCHAR(128) NOT NULL,
  endpoint VARCHAR(160) NOT NULL,
  request_hash CHAR(64) NOT NULL,
  response_status INTEGER,
  response_body JSONB,
  resource_id UUID,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_at TIMESTAMPTZ NOT NULL,
  UNIQUE (user_id, idempotency_key, endpoint)
);
CREATE INDEX IF NOT EXISTS idx_idempotency_expiry ON idempotency_records (expires_at);

COMMIT;

-- Post-migration checks (run separately):
-- SELECT publication_status, visibility, license_code, COUNT(*) FROM ideas GROUP BY 1,2,3;
-- SELECT relation_type, COUNT(*) FROM fork_relations GROUP BY 1;
-- SELECT COUNT(*) FROM ideas WHERE publication_status='published' AND visibility='public';

-- Operational requirements:
-- 1) Take backup and rehearse before production.
-- 2) Compare this proposal with the deployed schema; do not assume docs equal production.
-- 3) PG JSONB and recursive CTE require a separate SQLite implementation/test path.
-- 4) Publish transaction creates Idea + version + relations + contributor attribution + notifications.
-- 5) Roll back application code first; do not automatically drop additive tables or columns.
-- 6) Historical Ideas remain private with legacy_unspecified license until explicit migration policy.