# INC-2026-041: Checkout Lock Queue Outage from Migration 0009

- Namespace: `adlc/proj/contextcon-adlc/postmortems`
- Date: 2026-09-14
- Severity: SEV-1 (19 minutes degraded write latency)

## Summary

Migration `0009_add_ledger_lookup_idx.sql` executed `CREATE INDEX idx_journal_lines_ref ON journal_lines (reference_id);` without `CONCURRENTLY` and without `SET lock_timeout = '2s';`. While scanning 42M rows under a `SHARE` lock, concurrent settlement writers queued behind pending `ALTER` lock waiters, exhausting all 120 API worker connections across 3 availability zones.

## Root Cause

1. Developer copied a generic Postgres migration template without running `context_search` against ADR-001.
2. No automated PR review agent checked SQL migrations for `CONCURRENTLY`, `NO_TX` transaction opt-out, or `lock_timeout`.
3. Migration was never tested against an isolated copy-on-write database fork before production deployment.

## Action Items Verified Fixed

1. Enforce ADR-001 across all `.sql` files in static verification + PR-Review Drift Guard.
2. Add Meko gotcha under `adlc/repo/ledger-service/gotchas`: any Postgres DDL adding an index on `journal_lines` or `journal_entries` MUST start with `-- migrate:no-transaction`, configure `SET lock_timeout = '2s';` and `SET statement_timeout = '30s';`, and use `CREATE INDEX CONCURRENTLY IF NOT EXISTS`.
3. Validate every migration PR against a zero-copy AMP Postgres branch (`amp_branch_create`) prior to merge.
