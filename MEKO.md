# Meko Context Map for contextcon-adlc

This repository uses one shared Meko Cloud datapack (`contextcon-adlc`) across Claude Code, Codex, Cursor, and our automated PR-Review Drift Guard agent.

## Namespaces

- `adlc/proj/contextcon-adlc/adrs`: Architecture Decision Records (`ADR-001` through `ADR-006`) stored in the shared Knowledge Base.
- `adlc/proj/contextcon-adlc/postmortems`: Historical incident postmortems (`INC-2026-041`, `INC-2026-078`) explaining concrete production failures.
- `adlc/repo/ledger-service/gotchas`: Cross-agent learnings captured via `memory_add` and promoted via `memory_promote` when verified.

## Agent Operating Contract

1. Before editing any module or SQL migration under `target_repo/`, call `context_search` (omitting deprecated `scope` arguments) targeting `contextcon-adlc`.
2. When another agent handed off via Meko `conversation_id`, inspect prior decisions via `conversation_get` and fetch shared patches via `artifact_get`.
3. Whenever an agent verifies a codebase gotcha or schema pitfall, record it once via `memory_add` and promote durable team rules via `memory_promote`.
4. Log every planning, review, or verification turn via `conversation_add_message` including explicit `reasoning`, `plan`, and `metadata`, plus token telemetry via `track_token_usage`.
5. Keep secrets out of prompts, commits, artifacts, and logs. Never embed `MEKO_API_KEY` or Postgres passwords in tracked files.
