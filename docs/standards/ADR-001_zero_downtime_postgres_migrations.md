# ADR-001: Zero-Downtime Postgres Migrations and Lock Safety

- Status: Accepted
- Namespace: `adlc/proj/contextcon-adlc/adrs`
- Applies To: `target_repo/sql/migrations/*.sql`, migration helpers, schema tests

## Context

`ledger-service` processes high-frequency double-entry postings against PostgreSQL. Acquiring un-timed `ACCESS EXCLUSIVE` or `SHARE` locks on core tables stalls active payment transactions and triggers connection pool exhaustion across API workers.

## Mandatory Rules

1. **Rule ADR-001.1 (Concurrent Index Operations)**:
   - Never run bare `CREATE INDEX` or `DROP INDEX` on production tables.
   - Always specify `CREATE INDEX CONCURRENTLY IF NOT EXISTS ...` or `DROP INDEX CONCURRENTLY IF EXISTS ...`.
   - Index migrations must include `-- migrate:no-transaction` (marker token `NO_TX`) in the file header comment because Postgres rejects `CONCURRENTLY` inside a multi-statement transaction block.
2. **Rule ADR-001.2 (Explicit Lock and Statement Timeouts)**:
   - Every `.sql` migration script must configure both `SET lock_timeout = '2s';` and `SET statement_timeout = '30s';` before executing any `ALTER TABLE`, `CREATE INDEX`, or `DROP` statement.
   - Lock timeout protects live traffic from queuing behind blocked schema changes.
3. **Rule ADR-001.3 (Two-Phase Constraints without Table Rewrites)**:
   - Never add a `CHECK` or `FOREIGN KEY` constraint directly in locked mode, and never execute `ALTER TABLE ... ADD COLUMN ... NOT NULL` without safe validation.
   - When enforcing new validation constraints (`CHECK` or `FOREIGN KEY`), always add the constraint with `NOT VALID` first, then run `ALTER TABLE ... VALIDATE CONSTRAINT ...;` in a subsequent step (after lock timeout guard).
4. **Rule ADR-001.4 (Identity and Primary Keys)**:
   - Never use `SERIAL` or `BIGSERIAL` types in DDL.
   - Always use `UUID PRIMARY KEY DEFAULT gen_random_uuid()` for external entities or `BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY` for monotonic internal ledger journals.
5. **Rule ADR-001.5 (AMP Zero-Copy Branch Dry-Run)**:
   - Before merging any DDL migration PR, fork an isolated copy-on-write database branch in Meko AMP (`amp_branch_create`), attach temporary compute (`ingress_external` restricted strictly to explicit `/32` or `/24` IPv4 CIDRs), apply the migration twice to test idempotency, verify row invariants, and retire the ephemeral compute endpoint immediately afterward.

## Anti-Patterns Rejected During PR Review

- `CREATE INDEX idx_ledger_acct ON journal_lines (account_id);` (missing `CONCURRENTLY` and missing `SET lock_timeout`).
- `ALTER TABLE journal_lines ADD CONSTRAINT chk_pos CHECK (amount_minor > 0);` without `NOT VALID` + `VALIDATE CONSTRAINT`.
- Leaving out `SET lock_timeout = '2s';` or omitting `-- migrate:no-transaction` when using `CONCURRENTLY`.

## Extended Engineering Guidance

- Keep DDL migrations small, focused, and forward-only.
- If adding a nullable tracking column with a backfill, deploy the nullable column first, run batched application/worker backfill under `statement_timeout = '30s'`, then enforce `CHECK (col IS NOT NULL) NOT VALID` followed by `VALIDATE CONSTRAINT`.
- Always check `pg_locks` wait queues during branch simulation when adding foreign keys referencing `journal_entries` or `ledger_accounts`.
