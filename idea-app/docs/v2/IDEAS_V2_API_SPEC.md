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

所有接口均要求登录，且仅创意作者可访问；当前版本管理仅开放给 private、未归档、非 rejected 创意。

| Method | Path | Purpose |
|---|---|---|
| GET | `/ideas/{idea_id}/versions` | 查询版本历史及贡献署名 |
| POST | `/ideas/{idea_id}/versions/drafts` | 创建版本草稿 |
| PATCH | `/ideas/{idea_id}/versions/{version_id}` | 编辑草稿及贡献选择 |
| POST | `/ideas/{idea_id}/versions/{version_id}/publish` | 发布版本并更新 Idea.content |

创建/编辑草稿请求字段：`content`（1-300 字，作者整合后的最终文本）、`change_summary`（可选，最多 2000 字）、`contribution_ids`（可选，最多 50 个已采纳贡献 UUID）。

发布操作采用事务：锁定 Idea 和 draft version；复核所选贡献仍属于该 Idea 且状态为 accepted；将版本设为 published 并记录发布者/时间；同步更新 Idea.content。贡献归属表保存贡献作者 ID、用户名和贡献内容快照，用户名变更后历史署名不漂移。数据库唯一约束保证一条贡献最多被一个版本消费。

错误语义：404 表示不存在或无权访问；409 表示已有草稿、贡献未采纳/状态变化或版本冲突；422 表示内容为空或贡献 ID 重复；403 表示内容审核未通过。
