# IDEAS V2.0 Production Migration Runbook

**Status:** Review checklist only. No production database has been accessed or migrated.  
**Target:** PostgreSQL 16+  
**Migrations:** `001_idea_visibility_and_acl.sql` → `002_idea_contributions.sql` → `003_idea_versions_and_attribution.sql` → `004_collaborations.sql` → `005_collaboration_attribution.sql` → `006_idea_associations.sql` → `007_notification_preferences.sql` → `008_collaboration_member_leave.sql` → `009_collaboration_notification_links.sql` → `010_idea_reports.sql` → `011_user_follows.sql`

This runbook is not authorization to run migrations. Production execution requires an approved maintenance window, a named operator, a verified backup/restore rehearsal, and explicit approval of the legacy-public-data assumption below.

## 1. Release gates (all required)

- [ ] Confirm the exact deployed application commit and schema version.
- [ ] Compare the production schema with the migration assumptions; do not assume the repository schema matches production.
- [ ] Confirm PostgreSQL major version and database encoding.
- [ ] Confirm the production role can create tables, indexes, constraints, and use required UUID functions.
- [ ] Verify that the currently deployed application exposes every `ideas.status = 'active'` row publicly. Migration 001 converts **all** active rows to `published/public`; if this predicate does not exactly match the historical public-read policy, STOP and revise the backfill predicate before release.
- [ ] Approve the 90-day legacy license transition start date as the V2.0 activation/announcement effective date. The deadline is deployment configuration, not a date hard-coded in SQL.
- [ ] Confirm the unresolved product policy for legacy Ideas that remain unconfirmed after the 90-day period before implementing expiry behavior. No automatic expiry behavior is authorized by this runbook.
- [ ] Confirm no application instance that cannot tolerate the additive schema is running during the migration window.

## 2. Read-only preflight SQL

Run against production using a read-only account first. Save the outputs with the release record.

```sql
-- Database identity and server version
SELECT current_database() AS database_name,
       current_user AS connected_role,
       current_setting('server_version') AS server_version;

-- Existing tables required by Migration 001
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN ('users', 'ideas', 'fork_relations')
ORDER BY table_name;

-- Required legacy columns: these must already exist before Migration 001.
-- V2 columns such as publication_status / visibility / published_at are ADDED by 001;
-- they are not prerequisites for the migration.
SELECT table_name, column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'public'
  AND (
    (table_name = 'ideas' AND column_name IN
      ('id','status','created_at','author_id','is_forkable'))
    OR (table_name = 'fork_relations' AND column_name = 'id')
    OR (table_name = 'users' AND column_name = 'id')
  )
ORDER BY table_name, ordinal_position;

-- Detect any V2 columns that may have been partially added by an earlier/manual rollout.
-- Their presence is not a prerequisite; reconcile any partial rollout before proceeding.
SELECT table_name, column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'ideas'
  AND column_name IN (
    'publication_status','visibility','license_code','license_text_snapshot',
    'license_version','allow_fork','published_at','archived_at',
    'legacy_license_review_status','legacy_license_review_notified_at',
    'legacy_license_reviewed_at'
  )
ORDER BY ordinal_position;

-- Baseline lifecycle distribution
SELECT status, COUNT(*) AS row_count
FROM ideas
GROUP BY status
ORDER BY status;

-- Exact population that Migration 001 will make public
SELECT COUNT(*) AS active_rows_to_become_public
FROM ideas
WHERE status = 'active';

-- Inspect a bounded sample with owner and timestamps. Review against old public-read behavior.
SELECT id, author_id, status, created_at, is_forkable
FROM ideas
WHERE status = 'active'
ORDER BY created_at DESC
LIMIT 100;

-- Existing objects that could conflict with new names
SELECT to_regclass('public.app_schema_migrations') AS migration_registry,
       to_regclass('public.idea_access_grants') AS access_grants,
       to_regclass('public.idea_contributions') AS contributions,
       to_regclass('public.idea_versions') AS versions,
       to_regclass('public.idea_version_contributions') AS version_attributions,
       to_regclass('public.collaborations') AS collaborations,
       to_regclass('public.collaboration_members') AS collaboration_members,
       to_regclass('public.collaboration_sources') AS collaboration_sources,
       to_regclass('public.collaboration_contributions') AS collaboration_contributions,
       to_regclass('public.collaboration_events') AS collaboration_events,
       to_regclass('public.idea_associations') AS idea_associations;

-- If an app_schema_migrations table already exists, inspect it; do not overwrite it.
SELECT version, applied_at
FROM app_schema_migrations
ORDER BY applied_at, version;
```

The final query must only be run if the registry exists; otherwise skip it. Review all existing objects and migration markers manually. Any unexpected pre-existing object, missing required base column, or already-present marker is a STOP condition until reconciled.

## 3. Backup and restore rehearsal

1. Take a database-native full backup using the organization's approved tooling (for example, `pg_dump -Fc` for a custom-format logical backup).
2. Record backup timestamp, database identity, dump file size, checksum, and operator.
3. Verify the dump can be listed (for a custom-format dump, `pg_restore --list`).
4. Restore the backup into an isolated staging database using the same PostgreSQL major version.
5. Run the read-only preflight SQL against the restored copy.
6. Rehearse migrations 001 → 002 → 003 → 004 → 005 → 006 → 007 → 008 → 009 → 010 → 011 on that restored copy, then run the post-migration validation SQL below.
7. Confirm application smoke tests against the restored/migrated staging copy.
8. Do not proceed if restore or rehearsal fails. A backup that has not been restored is not a verified recovery point.

Actual backup commands, retention, encryption, storage destination, and RPO/RTO must follow the production operator's approved procedures; this repository does not contain production credentials or infrastructure configuration.

## 4. Execution sequence (operator only, after approval)

- Put the application into the approved maintenance/read-only mode if required by the release plan.
- Take and verify the final pre-migration backup.
- Execute each migration file in order using the approved PostgreSQL client with stop-on-error enabled (for example, `psql -v ON_ERROR_STOP=1`). Each file manages its own transaction.
- Stop immediately on the first error. Do not manually insert migration markers or skip prerequisites.
- Verify all eleven registry entries and post-migration invariants before enabling V2 endpoints.
- Keep the backup and logs according to the organization's retention policy.

Migration 001 intentionally rejects a second execution once its marker exists. Migrations 002–011 also check prerequisites. Do not edit markers to force a rerun.

## 5. Post-migration validation SQL

```sql
-- All eleven migrations must be recorded exactly once.
SELECT version, applied_at
FROM app_schema_migrations
WHERE version IN (
  '001_idea_visibility_and_acl',
  '002_idea_contributions',
  '003_idea_versions_and_attribution',
  '004_collaborations',
  '005_collaboration_attribution',
  '006_idea_associations',
  '007_notification_preferences',
  '008_collaboration_member_leave',
  '009_collaboration_notification_links',
  '010_idea_reports',
  '011_user_follows'
)
ORDER BY version;

-- Review resulting state distribution.
SELECT publication_status, visibility, legacy_license_review_status, COUNT(*)
FROM ideas
GROUP BY 1,2,3
ORDER BY 1,2,3;

-- Active rows should have the intended legacy transition state.
SELECT COUNT(*) AS active_rows_not_in_expected_state
FROM ideas
WHERE status = 'active'
  AND NOT (
    publication_status = 'published'
    AND visibility = 'public'
    AND legacy_license_review_status = 'pending'
    AND allow_fork = FALSE
  );

-- Non-active rows should remain private drafts under this migration policy.
SELECT COUNT(*) AS non_active_rows_not_in_expected_state
FROM ideas
WHERE status <> 'active'
  AND NOT (
    publication_status = 'draft'
    AND visibility = 'private'
    AND legacy_license_review_status = 'not_required'
    AND allow_fork = FALSE
  );

-- Verify expected new tables and constraints exist.
SELECT to_regclass('public.idea_access_grants') AS access_grants,
       to_regclass('public.idea_contributions') AS contributions,
       to_regclass('public.idea_versions') AS versions,
       to_regclass('public.idea_version_contributions') AS version_attributions,
       to_regclass('public.collaborations') AS collaborations,
       to_regclass('public.collaboration_members') AS collaboration_members,
       to_regclass('public.collaboration_sources') AS collaboration_sources,
       to_regclass('public.collaboration_contributions') AS collaboration_contributions,
       to_regclass('public.collaboration_events') AS collaboration_events,
       to_regclass('public.idea_associations') AS idea_associations;

SELECT conrelid::regclass AS table_name, conname, contype
FROM pg_constraint
WHERE conname IN (
  'uq_idea_versions_number',
  'uq_version_contribution_consumed_once',
  'uq_version_contribution_pair',
  'uq_idea_contribution_collaboration_source',
  'uq_idea_association_pair',
  'ck_idea_association_no_self',
  'ck_idea_association_type'
)
ORDER BY table_name, conname;
```

Both unexpected-row counts must be zero unless a separately approved data exception explains otherwise. Validate foreign keys and indexes against the migration files before enabling new endpoints.

## 6. Rollback and recovery

- Preferred first response to an application regression: disable/roll back the application release while retaining additive schema objects.
- Do not automatically drop new tables/columns or delete migration markers. Migration 001 rewrites publication/visibility fields and is not safely reversed by a generic `DROP COLUMN`.
- If data corruption or an unacceptable backfill result is detected, stop writes and follow the approved restore/recovery plan using the verified pre-migration backup. Coordinate point-in-time recovery with the database operator.
- Any manual data correction or schema rollback requires a separately reviewed, versioned SQL script and a fresh backup.
- Record the incident, affected rows, recovery point, and validation evidence.

## 7. Known limits

- CI has executed migrations against an isolated PostgreSQL 16 service database, not against production.
- CI cannot prove production schema parity, production row counts, lock duration, disk headroom, backup validity, or application compatibility with the deployed database.
- Migration 001's active-row backfill is a product/data-policy decision and must be approved against production's actual historical visibility semantics.
- The post-90-day treatment of legacy Ideas without confirmed authorization remains an open product decision.
