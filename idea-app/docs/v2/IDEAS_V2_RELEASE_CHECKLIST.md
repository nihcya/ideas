# IDEAS V2.0 Release Checklist

## Automated release candidate

The release workflow is manual and does not deploy automatically.

1. Merge the reviewed V2.0 branch after all required CI checks pass.
2. Configure these GitHub Actions repository secrets:
   - `ANDROID_KEYSTORE_BASE64`: base64-encoded Android upload keystore.
   - `ANDROID_KEYSTORE_PASSWORD`.
   - `ANDROID_KEY_ALIAS`.
   - `ANDROID_KEY_PASSWORD`.
3. Trigger **IDEAS V2 Release Candidate** from Actions → Run workflow.
4. Supply the production API base URL, including `/api`.
5. Download the `ideas-v2-release-candidate` artifact and verify the signed Android App Bundle and production Web build.
6. Configure production reverse proxy, HTTPS, API CORS, storage and database backups before deployment.

The debug APK produced by normal CI is a test artifact, not a store-ready package. The release workflow refuses to build if the Android upload keystore secrets are missing. Signing material is ignored by Git and must never be committed.

## Database and scheduled jobs

- Follow `IDEAS_V2_PRODUCTION_MIGRATION_RUNBOOK.md` and apply migrations 001–012 in order during an approved maintenance window.
- Migration 001 defines the V2.0 activation marker; Migration 012 derives the historical public-Idea authorization deadline as activation + 90 days.
- Schedule `python -m jobs.expire_legacy_license_reviews` daily from the backend working directory.
- Set `ADMIN_USER_IDS` to the comma-separated UUID allowlist for moderation administrators.
- Configure the normal production API URL as the `api_base_url` workflow input; do not use the local CI default.

## Not performed by CI

- No production database migration is executed.
- No production deployment or DNS/proxy changes are executed.
- No Android signing secrets are created or stored by this repository.
- No user data or production records are modified.
