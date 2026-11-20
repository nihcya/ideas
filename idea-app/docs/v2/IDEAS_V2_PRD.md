# IDEAS V2.0 PRD

Draft 1.0

## Product decisions
- New Ideas default to private drafts; public only after explicit publish.
- Authors choose a license; license is checked server-side before Fork or Collide.
- V2.0 collaboration is asynchronous; real-time co-editing is out of scope.

## Baseline
Existing Flutter + FastAPI + SQLAlchemy project. Reuse `ideas`, `fork_relations`, and `vault_items`; do not rebuild the graph layer.

## Important distinction
`ideas.status` remains lifecycle/moderation state. Add separate publication status (`draft`, `published`, `archived`) and visibility (`private`, `public`).