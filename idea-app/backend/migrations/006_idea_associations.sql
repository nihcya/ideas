-- IDEAS V2.0 / Migration 006: Inspired associations separate from strict lineage DAG
-- PostgreSQL 16+. Requires migrations 001..005.

BEGIN;

DO $migration$
BEGIN
  IF to_regclass('public.app_schema_migrations') IS NULL
     OR NOT EXISTS (SELECT 1 FROM app_schema_migrations WHERE version = '001_idea_visibility_and_acl')
     OR NOT EXISTS (SELECT 1 FROM app_schema_migrations WHERE version = '002_idea_contributions')
     OR NOT EXISTS (SELECT 1 FROM app_schema_migrations WHERE version = '003_idea_versions_and_attribution')
     OR NOT EXISTS (SELECT 1 FROM app_schema_migrations WHERE version = '004_collaborations')
     OR NOT EXISTS (SELECT 1 FROM app_schema_migrations WHERE version = '005_collaboration_attribution') THEN
    RAISE EXCEPTION 'Migrations 001..005 must be applied before 006';
  END IF;
END;
$migration$;

CREATE TABLE idea_associations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_idea_id UUID NOT NULL REFERENCES ideas(id) ON DELETE CASCADE,
  target_idea_id UUID NOT NULL REFERENCES ideas(id) ON DELETE CASCADE,
  relation_type VARCHAR(16) NOT NULL DEFAULT 'inspired' CHECK (relation_type = 'inspired'),
  created_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  note TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_idea_association_pair UNIQUE(source_idea_id, target_idea_id),
  CONSTRAINT ck_idea_association_no_self CHECK(source_idea_id <> target_idea_id)
);
CREATE INDEX idx_idea_associations_source ON idea_associations(source_idea_id, created_at);
CREATE INDEX idx_idea_associations_target ON idea_associations(target_idea_id, created_at);

INSERT INTO app_schema_migrations(version) VALUES ('006_idea_associations');

COMMIT;
