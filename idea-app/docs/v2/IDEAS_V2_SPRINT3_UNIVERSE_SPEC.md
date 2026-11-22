# IDEAS V2.0 Sprint 3 — Idea Universe

Status: bounded recursive graph API and separate Inspired association model/API are implemented; PostgreSQL migration and exact-head CI are pending.

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
