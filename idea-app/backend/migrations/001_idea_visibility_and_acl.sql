-- IDEAS V2.0 / Migration 001: publication, license review and direct Idea ACL
-- PostgreSQL 16+. MANUAL / REVIEW REQUIRED.
--
-- IMPORTANT:
-- 1. Take a verified backup and run the preflight queries before applying.
-- 2. Confirm that every currently active Idea was publicly readable under the deployed
--    production query rules. If not, replace the active-row backfill predicate explicitly.
-- 3. The 90-day legacy license transition deadline is supplied by deployment configuration
--    from the V2.0 activation/announcement effective date; no calendar deadline is hard-coded here.
-- 4. This file is not executed automatically by application startup.

BEGIN;

ALTER TABLE fork_relations ADD COLUMN IF NOT EXISTS metadata JSONB;

ALTER TABLE ideas
  ADD COLUMN IF NOT EXISTS publication_status VARCHAR(16) NOT NULL DEFAULT 'draft',
  ADD COLUMN IF NOT EXISTS visibility VARCHAR(16) NOT NULL DEFAULT 'private',
  ADD COLUMN IF NOT EXISTS license_code VARCHAR(32),
  ADD COLUMN IF NOT EXISTS license_text_snapshot TEXT,
  ADD COLUMN IF NOT EXISTS license_version VARCHAR(32),
  ADD COLUMN IF NOT EXISTS allow_fork BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS published_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS legacy_license_review_status VARCHAR(16) NOT NULL DEFAULT 'not_required',
  ADD COLUMN IF NOT EXISTS legacy_license_review_notified_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS legacy_license_reviewed_at TIMESTAMPTZ;

-- Preserve currently active content as public only after the preflight assumption is verified.
UPDATE ideas
SET publication_status = 'published',
    visibility = 'public',
    license_code = 'legacy_unspecified',
    allow_fork = FALSE,
    legacy_license_review_status = 'pending',
    published_at = COALESCE(published_at, created_at)
WHERE status = 'active';

-- Keep all other pre-existing content private and unpublished.
UPDATE ideas
SET publication_status = 'draft',
    visibility = 'private',
    license_code = COALESCE(license_code, 'legacy_unspecified'),
    allow_fork = FALSE,
    legacy_license_review_status = 'not_required'
WHERE status <> 'active';

CREATE INDEX IF NOT EXISTS idx_ideas_publication_visibility
  ON ideas (publication_status, visibility, status);
CREATE INDEX IF NOT EXISTS idx_ideas_legacy_license_review
  ON ideas (legacy_license_review_status);

CREATE TABLE IF NOT EXISTS idea_access_grants (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  idea_id UUID NOT NULL REFERENCES ideas(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role VARCHAR(16) NOT NULL DEFAULT 'viewer'
    CHECK (role IN ('contributor','viewer')),
  status VARCHAR(16) NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending','accepted','declined','revoked')),
  invited_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  invited_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  responded_at TIMESTAMPTZ,
  revoked_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (idea_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_idea_access_grants_user_status
  ON idea_access_grants (user_id, status);
CREATE INDEX IF NOT EXISTS idx_idea_access_grants_idea_status
  ON idea_access_grants (idea_id, status);

COMMIT;

-- Post-migration validation:
-- SELECT publication_status, visibility, legacy_license_review_status, COUNT(*)
-- FROM ideas GROUP BY 1,2,3 ORDER BY 1,2,3;
-- SELECT COUNT(*) FROM ideas WHERE status='active'
--   AND NOT (publication_status='published' AND visibility='public'
--            AND legacy_license_review_status='pending');
-- Verify no unexpected rows were converted before enabling V2 endpoints.
