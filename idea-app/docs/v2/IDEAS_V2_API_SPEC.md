# IDEAS V2.0 API Specification

- Version: Draft 1.1
- Base path: /api (existing FastAPI prefix)
- Authentication: existing JWT Bearer token
- Compatibility: retain existing v1 routes; add new endpoints without silently changing old semantics.

## 1. Global rules

### Access control
- Public reads must filter publication_status=published, visibility=public, status=active in SQL.
- Private Ideas and private collaborations are visible only to their owner and explicitly authorized members whose direct Idea invite or collaboration invite has been accepted.
- Collaboration membership does not implicitly grant access to every private source Idea; check the Idea ACL separately.
- Return 404 for inaccessible private resources to avoid existence disclosure.
- Frontend hiding is not authorization; every endpoint enforces permissions server-side.
- Fork, Collide, Evolve and collaboration publishing must validate source license and author settings.

### Idempotency
Write endpoints that create Ideas, Forks, collaborations or published results accept Idempotency-Key (UUID). Same key and same request returns the original result; same key with a different request returns 409. Store user, endpoint, request hash, response and expiry.

### Errors
Use existing envelope: { error: { code, message } }. Common status: 400 invalid input, 401 unauthenticated, 403 forbidden action, 404 inaccessible/missing resource, 409 conflict, 422 schema error, 429 rate limited, 503 AI unavailable.

## 2. Idea representation

Existing fields remain: id, content, source, author, status, fork_count, ai_assisted, created_at.
Add:
- publication_status: draft | published | archived
- visibility: private | public
- license_code: all_rights_reserved | attribution | attribution_adaptation | custom | legacy_unspecified
- license_text_snapshot, license_version, published_at, archived_at, allow_fork
- legacy_license_review_status: not_required | pending | confirmed | expired (or equivalent state machine)
- legacy_license_review_notified_at, legacy_license_reviewed_at (audit timestamps)

License codes are implementation placeholders; legal wording and availability must be confirmed before public launch. Historical records migrate to legacy_unspecified and must not gain broader rights automatically. Existing active Ideas that were publicly visible before V2 are backfilled as published + public, with legacy_license_review_status=pending. During the 90-day transition period, starting from the V2.0 activation/announcement effective date, they remain publicly readable but cannot be newly Forked/Collided/Evolved until the author confirms a license. The deployment configuration supplies the single deadline; expiry handling for unconfirmed Ideas remains a product decision.

## 3. Idea endpoints

### POST /api/ideas
Create a private draft. Request: { content: string(1..300) }. Response 201 includes id, content, publication_status=draft, visibility=private, status and created_at. Preserve current audit and Vault behavior, but do not expose the new Idea publicly.

### PATCH /api/ideas/{id}
Update the author's own draft. Request: { content }. Published content must use a versioned edit workflow. Update version snapshot and re-run content moderation where required.

### POST /api/ideas/{id}/publish
Request: { visibility: public, license_code, license_custom_text?, allow_fork, confirm_terms: true }. Response: published Idea. Author-only; validate license; run moderation; write audit/event; invalidate public caches. Public visibility only begins after this explicit action.

### POST /api/ideas/{id}/unpublish
Author-only. Moves a published Idea back to private draft or an equivalent withdrawn state, removes it from Explore/search/public graph immediately, preserves relations and audit history, and invalidates caches.

### GET /api/ideas/explore
Retain limit/offset. Return only published + public + active Ideas. Fix current hot/random overlap by deduplicating IDs. Never expose draft/private content.

### GET /api/ideas/{id}
Guests may read public Ideas. Owners and accepted direct-invite/collaboration members may read authorized private Ideas. Include publication metadata, license, lineage relation types and contributors.

### POST /api/ideas/{id}/invites
Author-only. Request: { user_id, role: contributor|viewer }. Creates a pending direct access grant for this private Idea. A pending invite grants no read access.

### POST /api/ideas/{id}/invites/{invite_id}/accept
Invitee-only. Accepts the pending grant; subsequent reads are authorized according to the granted role. Revocation by the author immediately removes access.

### GET /api/ideas/{id}/lineage
Query: depth=1..3 (default 2), direction=ancestors|descendants|both, limit=1..100 (default 50). Response: { root_id, nodes: [], edges: [], truncated }. Apply access control within recursive query and do not leak private node identifiers or titles.

### POST /api/ideas/{id}/fork
Request: { content, fork_type: improvement|extension|scenario_shift|reverse_thinking, note?, ai_assisted? }. Response 201 with new Idea and parent_id. Parent must be public, published, active, fork-enabled and licensed for the requested derivative use. A legacy public Idea with license review pending remains readable during the 90-day transition but cannot be newly Forked. In one transaction create Idea, relation, VaultItem, attribution/license snapshot, notification and atomic fork_count increment.

### Collide and Evolve
Keep existing POST /api/ideas/collide, /collide/confirm, /evolve and /evolve/confirm routes. Add source visibility and license validation before AI generation and before creating a derivative. Merge creates two parent edges. Multi-user results must publish through collaboration workflow. A legacy public source with license review pending cannot be used for new Collide/Evolve operations.

## 4. Collaboration endpoints

### POST /api/collaborations
Request: { title, description?, source_idea_ids: [uuid], visibility: private }. Response 201: collaboration id, status=draft, owner_id, member_role=owner. Validate that owner can access all source Ideas.

### POST /api/collaborations/{id}/members
Owner invites a user: { user_id, role: contributor|viewer }. Invite state starts pending. Pending users do not gain access to private materials.

### POST /api/collaborations/{id}/accept
Invitee accepts. Response includes member role and accepted status.

### GET /api/collaborations/{id}
Member-only collaboration details: state, member roles, contribution summaries and permitted source Idea summaries.

### POST /api/collaborations/{id}/contributions
Accepted contributor/owner submits { content, contribution_type: idea|revision|comment|research, source_idea_id?, ai_assisted? }. Each contribution is attributable and versioned.

### PATCH /api/collaborations/{id}/contributions/{contribution_id}
Contributor may update own unlocked contribution. Owner may accept/reject with review metadata but cannot impersonate the contributor.

### POST /api/collaborations/{id}/publish
Owner confirms final publication: { content, visibility, license_code, allow_fork, accepted_contribution_ids, confirm_terms: true }. In one transaction validate source licenses and accepted contributions; create Idea, IdeaVersion, parent relations, contributor attribution, notifications; mark collaboration published. Roll back all on failure.

## 5. Contributors and notifications

GET /api/ideas/{id}/contributors returns contributors with user_id, username, role and contribution_count; private Idea requires access.
Extend notification types with collaboration_invited, contribution_submitted, contribution_accepted, contribution_rejected and collaboration_published. Retain existing notification list/read APIs.

## 6. Withdrawal and derivative continuity

- Unpublishing/withdrawing a parent Idea removes that parent from public discovery immediately; it does not cascade-delete existing child Ideas.
- Existing derivative Ideas retain attribution, parent edge and immutable license/attribution snapshot captured when the derivative was created.
- An existing derivative may remain public only to the extent the source license snapshot and any other parent licenses permit public redistribution. If the snapshot is missing, ambiguous or does not permit it, restrict the derivative from public discovery pending rights review; preserve it for its author and authorized members.
- No new derivative may be created from an unpublished/withdrawn parent. A parent withdrawal does not silently broaden the derivative's rights.

## 7. Compatibility and rollout

- Keep existing routes and fields during migration.
- Retain is_forkable as a compatibility projection, not the sole authorization decision.
- Existing active Ideas that were publicly visible before V2 remain published + public during a configurable license-completion transition period and are marked review pending.
- During that transition, legacy public Ideas remain readable but cannot be newly Forked/Collided/Evolved until license confirmation.
- Historical inactive/rejected content is not automatically published.
- Old clients must not accidentally publish content. Update the Flutter Create flow to save draft and call the explicit publish endpoint.
- Do not switch public Explore to the new predicate until public content has been reviewed and republished.

## 8. Acceptance tests

1. Guest cannot read private Idea (404).
2. Private Idea never appears in Explore, public profile or public lineage; direct invite access is denied until accepted and revoked immediately after revocation.
3. Existing active public Ideas remain public after migration and are marked license review pending; new derivatives from them are blocked until license confirmation.
4. Withdrawing a parent does not delete existing derivatives; attribution and license snapshots remain and govern derivative visibility and future use.
5. Pending invite cannot read private collaboration.
6. Disallowed license blocks Fork/Collide/Evolve server-side.
7. Fork creates a new node and one parent edge; Merge creates two parent edges.
8. Repeated Idempotency-Key does not duplicate resources.
9. Collaboration publish is atomic across Idea, version, relations and contributors.
10. Lineage obeys depth/node limits and permission filtering.

## 9. Direct private-Idea access grants

Persist direct invites independently from collaboration membership. Suggested table: idea_access_grants(idea_id, user_id, role, status, invited_by, invited_at, responded_at, revoked_at), unique on (idea_id, user_id). Access is granted only when status=accepted and not revoked. Owner can revoke at any time. Every endpoint that returns Idea content, versions, lineage or attachments must call the same authorization service.


## 版本管理 API（第一阶段）

版本管理接口要求登录且仅创意作者可访问。可管理私有工作态创意，以及同时满足 `visibility=public`、`publication_status=published`、`status=active` 的公开创意。

| Method | Path | Purpose |
|---|---|---|
| GET | `/ideas/{idea_id}/versions` | 查询版本历史及贡献署名 |
| POST | `/ideas/{idea_id}/versions/drafts` | 创建版本草稿 |
| PATCH | `/ideas/{idea_id}/versions/{version_id}` | 编辑草稿及贡献选择 |
| POST | `/ideas/{idea_id}/versions/{version_id}/publish` | 发布版本并更新 Idea.content |

创建/编辑草稿请求字段：`content`（1-300 字，作者整合后的最终文本）、`change_summary`（可选，最多 2000 字）、`contribution_ids`（可选，最多 50 个已采纳贡献 UUID）。

发布操作采用事务：锁定 Idea 和 draft version；复核所选贡献仍属于该 Idea 且状态为 accepted；将版本设为 published 并记录发布者/时间；同步更新 Idea.content。贡献归属表保存贡献作者 ID、用户名和贡献内容快照，用户名变更后历史署名不漂移。数据库唯一约束保证一条贡献最多被一个版本消费。

错误语义：404 表示不存在或无权访问；409 表示已有草稿、贡献未采纳/状态变化或版本冲突；422 表示内容为空或贡献 ID 重复；403 表示内容审核未通过。


### 版本与贡献反向追溯补充

- `GET /ideas/{idea_id}/contributions` 在原有贡献字段外增加 `published_version`（仅当贡献已归属已发布版本时返回），包含版本 ID、版本号、发布时间和变更说明。
- 同一响应增加 `attribution_content_snapshot` 与 `attribution_author_name`，用于核对发布时冻结的贡献文本和署名；草稿关联不会向协作者暴露为已发布归属。
- 版本历史中的每个版本返回 `attributions[]`，包含 contribution_id、author_id、author_name、content。版本详情页展示完整贡献文本快照，而不只是贡献者名字。
- Flutter 贡献记录可以跳转到具体版本；版本草稿选择器会禁用已经归属已发布版本的贡献。


## 贡献者公开主页记录

### GET /api/users/{user_id}/contributions

公开查询用户已正式纳入**公开、已发布、active Idea 版本**的贡献署名记录。无需登录；支持 `limit`（1–100，默认 20）和 `offset`（默认 0）。

响应：
- `items[]`：署名 ID、Idea ID、版本快照内容、版本 ID/编号、发布时间、变更说明、冻结的贡献内容快照和作者名快照。
- `total`、`limit`、`offset`、`has_more`：分页元数据。

隐私约束：
- 仅返回 `IdeaVersion.status=published` 且关联 Idea 同时满足 `publication_status=published`、`visibility=public`、`status=active` 的署名。
- 私有 Idea 的贡献、版本草稿中的贡献关联、未公开/撤回/非 active Idea 的记录不出现在公开主页。
- 署名使用版本发布时冻结的作者名和贡献内容，不回读可变的贡献正文来重写历史。


## 公开创作者主页与版本时间线

### GET /api/users/{user_id}/contributions

公开查询指定用户在当前仍公开的创意中，已正式纳入已发布版本的贡献署名记录。支持 `limit`（1–100，默认 20）和 `offset`（默认 0），响应包含 `items`、`total`、`limit`、`offset`、`has_more`。只返回冻结的贡献内容和作者名快照；所属 Idea 必须同时满足 published + public + active。

### GET /api/ideas/{idea_id}/versions/public

公开只读版本时间线，无需登录。仅当 Idea 当前同时满足 `publication_status=published`、`visibility=public`、`status=active` 时返回数据；只返回 `IdeaVersion.status=published` 且 `IdeaVersion.published_at >= Idea.published_at` 的版本和发布时冻结的贡献署名快照；创意转为公开之前的私有版本不会被追溯公开。私有、未发布、撤回/非 active Idea 统一返回 404。该接口不提供草稿、编辑、发布或版本差异修改能力。



## 公开创意持续版本管理（2026-11-20 产品决策）

版本管理 API 在保持作者专属访问的前提下，支持两类创意：
- 私有工作态创意：沿用现有未归档、非 rejected 的私有创意规则。
- 公开创意：必须同时满足 `visibility=public`、`publication_status=published`、`status=active`。

公开创意作者可调用版本列表、创建草稿、编辑草稿、发布版本和版本差异接口。非作者统一返回 404。公开版本发布仅更新 `Idea.content` 和版本快照，不改变可见性、发布状态、授权字段或衍生权限字段。

公开只读时间线仍只返回 `IdeaVersion.status=published` 且 `IdeaVersion.published_at >= Idea.published_at` 的版本；转为公开之前发布的私有阶段版本不追溯公开。公开创意被撤回、归档或状态不再 active 后，版本写入接口拒绝操作。



### 公开时间线与贡献主页的前端导航约定

- 公开主页贡献列表使用 `GET /api/users/{user_id}/contributions` 的分页元数据，按 `limit=20`、`offset` 增量加载；必须保留服务端的 `total`、`has_more`。
- 点击贡献记录时，前端携带 `version_id` 导航至 `/idea/{idea_id}/timeline?version={version_id}`。
- 时间线页面仍调用公开只读接口，不以 query 参数绕过服务端可见性检查；`version` 参数只用于定位/展开目标版本。
- 深链目标若不在当前公开时间线结果中（例如创意已撤回或版本不属于公开阶段），页面不得显示私有快照。

## 8. Implemented private collaboration and version-publication contract (2026-11-22)

### Contribution withdrawal and review
- DELETE /api/ideas/{idea_id}/contributions/{contribution_id} is available only to the contribution author while the record is submitted and the user still has an accepted contributor grant for the private Idea.
- A revoked contributor receives HTTP 403; a contribution that is accepted, rejected, or already withdrawn is locked and cannot be withdrawn again.
- PATCH is likewise limited to the contribution author, submitted state, and current accepted contributor access.
- Only the Idea owner may review a submitted contribution. Accepted/rejected records are immutable through contributor edit/withdraw endpoints.

### Version publication failure behavior
- Publishing a version rechecks that every associated contribution still belongs to the same Idea and remains accepted.
- If a contribution state changed after draft creation, publication returns HTTP 409; the Idea content and draft publication state remain unchanged.
- The Idea content update, version status transition, published metadata, and frozen attribution associations are committed in one database transaction. A failed commit must be rolled back by the request transaction boundary.
- A contribution can be consumed by at most one version (database unique constraint on contribution_id); duplicate contribution IDs within one draft request are rejected with HTTP 422.
- Separate submissions remain separate proposals; identical text is not automatically deduplicated.

### Verification boundary
- ASGI HTTP tests cover the invite/contribution/publication flow and the permission/failure cases above.
- Current CI for code head b784036c5166e3cdc3ea2aec94cdbc9ffb2efdd0: Backend 51 passed; Flutter test/analyze passed; Android Debug APK build was still running at documentation time.
- PostgreSQL migrations 001/002/003 have not been executed. SQLite tests and simulated rollback do not replace PostgreSQL migration, concurrency, or production integration tests.

### Withdrawn-source lineage response privacy contract（2026-11-22）

The GET /api/ideas/{id} response returns lineage parent/child nodes with relation_type, license_snapshot, and is_navigable.
- If the viewer can still access a parent Idea, id is its Idea ID and is_navigable=true.
- If a parent was later withdrawn/unpublished and is no longer accessible, the API returns a generic withdrawn-source title, the frozen source author attribution and license snapshot, and an opaque withdrawn:<relation-id> key with is_navigable=false.
- The opaque key is only a graph-layout identity; it is not the private Idea ID and must never be used to request an Idea detail route.
- The Flutter lineage graph renders the historical source node but does not navigate to it.
- Do not return the withdrawn source's title/body or private Idea ID to a viewer who no longer has access.

## 9. Derivative license inheritance and multi-parent intersection contract（2026-11-22）

### Effective rights
- The effective rights of a published Idea are the union of its immutable lineage records as obligations, evaluated conjunctively: every direct parent and every ancestor in every parent chain must allow derivation.
- For a multi-parent Collide/Merge, the effective permission is the intersection of all parent chains. If any source has allow_fork=false or a license code outside attribution_adaptation/custom, creation is rejected; another parent's permissive terms cannot override it.
- The current Idea's own license applies only to the author's original contribution. It is appended to the effective chain for future derivation checks and never replaces upstream terms.

### Derivation endpoints
- POST /api/ideas/fork accepts confirm_custom_licenses (boolean, default false).
- POST /api/ideas/collide/confirm accepts confirm_custom_licenses (boolean, default false).
- POST /api/ideas/evolve/confirm accepts confirm_custom_licenses (boolean, default false).
- If any direct or inherited source uses custom, the caller must explicitly set confirm_custom_licenses=true. Otherwise return HTTP 422 with error code CUSTOM_LICENSE_CONFIRMATION_REQUIRED.
- Each created ForkRelation freezes its source's full rights_chain and custom-license acknowledgement (acknowledged, acknowledged_by, acknowledged_at), alongside the direct source license and attribution snapshot.
- attribution_adaptation may be passed downstream subject to preserving source attribution and every ancestor's permission.
- custom is never silently treated as an open license; the explicit confirmation is required on each derivative creation operation. A custom source still must have allow_fork=true.

### Publication
- When publishing a derivative with allow_fork=true, the server checks every inherited source obligation. If any ancestor blocks derivation or has an incompatible license, return HTTP 422 / INHERITED_LICENSE_BLOCKS_DERIVATION.
- A derivative author's selected license cannot broaden, replace, or waive upstream source terms.
- These rules use the existing ForkRelation JSON metadata; no additional migration is introduced by this contract.


## Collaboration workspace APIs (Sprint 2)

First-class asynchronous workspaces are independent of per-Idea invitations. See IDEAS_V2_SPRINT2_COLLABORATION_SPEC.md for full access matrix and atomic publication contract.

- GET /collaborations — list accepted workspaces for current user.
- POST /collaborations — create private workspace from 1–10 Ideas the owner can currently view; capture immutable source rights snapshots.
- GET /collaborations/invitations/inbox — list pending workspace invitations.
- GET /collaborations/{id}/members/search?q= — owner-only username search; excludes self and pending/accepted members; returns only user_id/username.\n- POST /collaborations/{id}/members — owner invites contributor/viewer.
- POST /collaborations/{id}/accept — accept invitation; workspace access only, no private source Idea ACL grant.
- POST /collaborations/{id}/decline — decline pending invitation.
- DELETE /collaborations/{id}/members/{user_id} — owner revokes pending/accepted membership.\n- DELETE /collaborations/{id}/leave — accepted non-owner leaves; membership changes to left and access is immediately revoked.\n- POST /collaborations/{id}/archive — owner archives draft/published workspace; operation is idempotent and freezes further writes while preserving history.
- GET /collaborations/{id} — accepted member reads workspace; owner sees all contributions, contributor sees own; private source details are independently ACL-filtered.
- POST /collaborations/{id}/contributions — owner/contributor submits attributed proposal.
- PATCH /collaborations/{id}/contributions/{contribution_id} — author edits own submitted proposal.
- DELETE /collaborations/{id}/contributions/{contribution_id} — author withdraws own submitted proposal.
- POST /collaborations/{id}/contributions/{contribution_id}/review — owner accepts/rejects proposal.

Pending members cannot read workspace. Viewer members cannot submit, edit, withdraw, or review contributions. Owner-only candidate search is rate-limited. A member may leave voluntarily; the owner cannot leave and must archive the workspace instead. Archived workspaces remain readable by accepted members but are read-only. Owner-only atomic publication into Idea/version/relations/attributions is implemented; exact-head CI and PostgreSQL race verification remain required.

- POST /collaborations/{id}/publish — owner-only atomic publication. Request includes final content, visibility, license, allow_fork, confirm_terms, confirm_custom_licenses and accepted_contribution_ids. Every source is locked and revalidated against current public status and full inherited rights chain; multi-parent obligations are intersected. Creates output Idea, initial version, parent edges, bridge IdeaContribution records and frozen version attributions in one transaction. Private output remains a private draft; public output requires explicit terms confirmation.


## Idea Universe APIs (Sprint 3)

- GET /ideas/search?q=&limit= — ACL-safe text search for public or currently accessible Ideas; max 50 results.\n- GET /ideas/{idea_id}/graph — bounded BFS traversal of strict parent→child lineage plus optional Inspired edges; default depth 2, max depth 3, max 100 nodes and 300 edges. ACL is checked server-side for every node. Restricted upstream ancestors use opaque non-navigable placeholders with sanitized frozen attribution; private descendants/associations are omitted.
- POST /ideas/{target_idea_id}/associations — target owner records an Inspired association from a viewable source Idea. Self-links are rejected, duplicate pair returns 409. Inspired is not ForkRelation and grants no derivative rights.
- DELETE /ideas/{target_idea_id}/associations/{association_id} — target-owner deletion.

See IDEAS_V2_SPRINT3_UNIVERSE_SPEC.md for traversal, privacy and edge contracts.


## Notification preferences and collaboration deep links (Sprint 4)

- GET /notifications/preferences — returns all supported notification types; a missing preference row defaults to enabled.
- PUT /notifications/preferences — upserts a partial set of notification_type/enabled values; duplicate or unknown types are rejected.
- GET /notifications — applies both current resource ACL and notification preference filters before pagination and unread aggregation.
- POST /notifications/read — uses the same ACL and preference filters; a disabled or inaccessible notification cannot be marked read.
- Collaboration invite, contribution review, and publication notifications carry collaboration_id. Private collaboration notifications are visible only while the recipient has a pending invitation or accepted membership; public Idea-linked notifications continue to follow the Idea ACL.
- Flutter deep links route pending collaboration invitations to the collaboration inbox, public published results to the Idea detail, and private collaboration updates to the workspace.
- Migration 007 stores notification preferences; Migration 009 adds the collaboration notification foreign key. Migration 008 is the explicit member-left lifecycle state.


## Public creator discovery (Sprint 4)

- GET /users/search?q=&limit=&offset= — search usernames with a minimum two-character query; returns public profile fields and counts derived only from active published public Ideas and published public-version attributions.
- Search results exclude accounts with no public Ideas and no public credited contributions. Ranking prioritizes public contribution count, then public Idea count, then username for stable ordering.
- Selecting a result opens the existing public creator profile, which paginates frozen public contribution attributions and links back to public Ideas.


## Community reports and moderation (Sprint 4)

- POST /reports — authenticated user submits a report for an Idea they can currently access; duplicate open reports by the same reporter/Idea are rejected.
- GET /reports/admin?status=&limit=&offset= — allowlisted moderators only; paginated queue includes the reported public content and reporter identity.
- POST /reports/admin/{report_id}/review — allowlisted moderators only; status transitions to in_review/resolved/dismissed; terminal reports cannot be processed again.
- A resolved report may set hide_idea=true. This changes the Idea to a private draft, disables further derivation, invalidates Explore and detail caches, and records the action in SecurityEvent.
- Admin authorization is controlled by server-only IDEAS_ADMIN_USER_IDS (comma-separated UUIDs). Empty/invalid allowlists deny all moderation access. No client endpoint can grant admin status.
