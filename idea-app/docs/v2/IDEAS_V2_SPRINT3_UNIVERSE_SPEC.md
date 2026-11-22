# IDEAS V2.0 Sprint 3 — Idea Universe

Status: bounded recursive graph API, separate Inspired association model/API, PostgreSQL migration 006, Flutter Universe graph screen, and ACL-safe Inspired source picker/management are implemented. Exact-head CI and remaining graph performance verification are pending.

## Product boundary

The Idea Universe is a navigable local graph around an Idea, not a new permission system. The existing ForkRelation DAG remains the authoritative lineage graph. Inspired is a separate, non-lineage association and MUST NOT affect derivative rights, license inheritance, attribution obligations, or DAG cycle checks.

## Graph API

GET /api/ideas/{idea_id}/graph

Query parameters:
- depth: default 2, allowed 1–3.
- direction: both (default), ancestors, descendants.
- include_inspired: default true.
- max_nodes: default 100, allowed 10–100; response edge cap 300.

Response contains root_id, depth, direction, include_inspired, nodes, edges and truncated. Nodes include depth, node_type, is_root and navigable. Edges preserve source/target direction and relation type. The server enforces ACL for every traversed node; client-side hiding is not a security boundary.

## Privacy rules

- A private root is returned only to a user who can view it.
- Private descendants and private Inspired associations are omitted from a public graph.
- An inaccessible upstream lineage node may be represented by an opaque, non-navigable placeholder only when a frozen lineage/license snapshot exists. The placeholder preserves frozen author display and rights information but never returns the original private Idea ID, title, content or author ID.
- Snapshot sanitization removes internal Idea/User identifiers from restricted placeholders.
- No graph result is cached in shared public cache; private and public graph responses cannot cross-contaminate.

## Inspired association

POST /api/ideas/{target_idea_id}/associations
- Only the target Idea owner can create the association.
- Request identifies source_idea_id and optional note.
- Self-association is rejected; duplicate source/target pair returns 409.
- Both endpoints must be viewable by the creator.
- Association is directed source → target and is shown only to viewers who can view both endpoints.
- DELETE /api/ideas/{target_idea_id}/associations/{association_id} is owner-only.
- Association is not a ForkRelation and grants no rights to either Idea.

## Bounded traversal

The server performs breadth-first traversal with visited-node tracking and a maximum depth of 3, node cap 100 and edge cap 300. A visited set prevents infinite traversal if historical data contains a cycle. Lineage edge direction is always parent → child; Inspired direction is source → target. Traversal does not modify source rows or permissions.

## Verification

Tests cover depth 2 recursion, ancestors/descendants, merge/evolve edge types, Inspired separation, depth validation, hidden private ancestor redaction, target-owner-only association creation, self-link rejection, duplicate handling and deletion. PostgreSQL migration 006 adds the independent association table and is required to run after migrations 001–005.


## Frontend and query implementation update（2026-11-22）

- The Idea detail page links to a dedicated Universe screen.
- The screen supports depth 1–3, ancestors/descendants/both, Inspired visibility, zoom/pan, relation labels, restricted non-navigable source placeholders, retry and truncation messaging.
- The client uses the dedicated UniverseService; graph responses are not put into a shared cache.
- Server-side node ACL checks are batched per BFS layer to avoid per-node ACL queries while retaining the same visibility predicate.
- Widget/API regression tests cover restricted placeholder rendering and directional traversal.
- Still open: graph query benchmarks and cap stress tests, responsive layout validation, and exact-head CI.


## ACL-safe Inspired source picker

GET /api/ideas/search
- Query parameters: q (trimmed length 2–80), limit (1–30, default 20).
- Anonymous users search only published + public + active Ideas.
- Authenticated users additionally search their own Ideas and Ideas with an accepted direct IdeaAccessGrant.
- Results contain only id, title excerpt, author display name and color; no private content is returned unless the viewer already has Idea access.
- The Universe router is registered before the dynamic one-segment Idea detail route so /ideas/search resolves correctly.

The Universe screen exposes add/remove association controls only when the current viewer owns the target Idea. Adding an association searches accessible source Ideas, optionally captures a short note, and then calls the owner-only association API. The backend remains the final authorization boundary.


The initial graph canvas width now scales with the widest BFS layer to prevent dense node overlap. The owner association list is height-bounded and independently scrollable. Widget tests exercise the Inspired search-and-create flow.
