# IDEAS V2.0 Sprint 2 — First-class asynchronous collaboration

Status: backend workspace foundation and initial Flutter workspace UI implemented; owner-controlled atomic publication and expanded PostgreSQL race coverage remain in progress.

## Product boundary

A Collaboration is a first-class asynchronous workspace, not an alias for a private Idea invitation. It may reference one or more source Ideas and records accepted members, attributed proposals, reviews, and a chronological event stream.

Workspace membership is deliberately separate from idea_access_grants. Accepting a Collaboration invitation grants access to the workspace only. It never grants access to a private source Idea, its text, versions, attachments, or private lineage.

No real-time chat, simultaneous editing, or project-management suite is included in V2.0.

## Data model

- collaborations: owner, title, description, draft/published/archived state, visibility, and the Idea created on publication.
- collaboration_members: unique (collaboration_id, user_id), role (owner/contributor/viewer), invitation state and timestamps.
- collaboration_sources: ordered source Ideas and immutable rights/attribution snapshots captured when the workspace is created.
- collaboration_contributions: attributed proposal, type, optional source Idea, review state and reviewer snapshot fields.
- collaboration_events: append-only event timeline.

PostgreSQL migration: 004_collaborations.sql. It requires 001, 002 and 003 and is included in the disposable PostgreSQL migration CI test. SQLite test databases use SQLAlchemy metadata creation.

## API

| Method | Path | Contract |
|---|---|---|
| GET | /api/collaborations | Current user's accepted workspaces |
| POST | /api/collaborations | Create private draft workspace; caller must be able to view every source |
| GET | /api/collaborations/invitations/inbox | Current user's pending workspace invitations |
| POST | /api/collaborations/{id}/members | Owner invites contributor/viewer |
| POST | /api/collaborations/{id}/accept | Invitee accepts; grants workspace membership only |
| POST | /api/collaborations/{id}/decline | Invitee declines |
| DELETE | /api/collaborations/{id}/members/{user_id} | Owner revokes member or pending invitation |
| GET | /api/collaborations/{id} | Accepted members only; contributors see own proposals, owner sees all |
| POST | /api/collaborations/{id}/contributions | Owner/contributor submits attributed proposal |
| PATCH | /api/collaborations/{id}/contributions/{contribution_id} | Author edits own submitted proposal |
| DELETE | /api/collaborations/{id}/contributions/{contribution_id} | Author withdraws own submitted proposal |
| POST | /api/collaborations/{id}/contributions/{contribution_id}/review | Owner accepts/rejects a submitted proposal |

## Access matrix

| Action | Owner | Contributor | Viewer | Pending invite |
|---|---:|---:|---:|---:|
| Read workspace | Yes | Yes | Yes | No |
| Read all proposals | Yes | No | No | No |
| Read own proposals | Yes | Yes | No | No |
| Submit proposal | Yes | Yes | No | No |
| Edit/withdraw own submitted proposal | Yes | Yes | No | No |
| Review proposals | Yes | No | No | No |
| Invite/revoke members | Yes | No | No | No |
| Read private source Idea | Only via its own Idea ACL | Only via its own Idea ACL | Only via its own Idea ACL | No |

Inaccessible workspace and source resources use 404 to avoid existence disclosure. Private source IDs and rights snapshots are omitted from workspace responses when the member does not independently have source access.

## Publication contract — next implementation tranche

The workspace owner alone publishes. The final operation must be a single database transaction that:
1. Locks the workspace, its source rows and accepted contribution rows.
2. Rechecks workspace owner/status and every source's current publication state, visibility, license chain and custom-term acknowledgement.
3. Requires every direct parent and every ancestor obligation to permit the intended derivative; multi-parent rights are the intersection, never a union.
4. Creates the output Idea, its initial immutable IdeaVersion, all parent ForkRelation edges and frozen rights/attribution snapshots.
5. Creates frozen IdeaVersionContribution records for accepted contributions selected by the owner.
6. Writes collaboration publication state, notifications and timeline event.
7. Rolls back every write if any check, moderation step, unique constraint or commit fails.

A private publication creates a private draft Idea unless the owner explicitly chooses public and confirms license terms. A downstream license cannot relax any source obligation. If any source chain includes custom terms, the owner must explicitly acknowledge them.

## Verification

Initial HTTP tests cover creation, pending invite denial, accept, viewer write denial, and the fact that workspace membership does not expose a private source Idea. PostgreSQL migration 004 is included in migration-order tests. Additional required tests: revocation-vs-write, accept-vs-revoke, publish-vs-source-unpublish, multi-parent rights intersection, atomic rollback, and frozen attribution.
