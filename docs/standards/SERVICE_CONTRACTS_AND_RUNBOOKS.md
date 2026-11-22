# Service Contracts and Operational Runbooks (ledger-service)

- Namespace: `adlc/proj/contextcon-adlc/adrs`
- Applies To: All runtime endpoints, migration workflows, webhook consumers, and background retry workers

## 1. Settlement Lifecycle State Machine

1. Every ledger transfer follows monotonic transitions: `PENDING -> AUTHORIZED -> SETTLED` or `PENDING -> FAILED`.
2. Terminal states `SETTLED` and `FAILED` are immutable. Refunds never mutate original `journal_entries`; instead they append balanced compensating `JournalEntry` rows linked via `parent_entry_id` and bounded by remaining refundable `amount_minor` (`ADR-002.4`).
3. Every command requires `(tenant_id, idempotency_key)` verified inside the same serializable or row-locked database unit of work before allocating `entry_id`.

## 2. Standard Migration Execution Runbook

1. Inspect affected table row estimates and foreign keys before editing `target_repo/sql/migrations/`.
2. Prepend `-- migrate:no-transaction` (`NO_TX`) whenever using `CREATE INDEX CONCURRENTLY` or `DROP INDEX CONCURRENTLY`.
3. Begin every migration file with `SET lock_timeout = '2s';` and `SET statement_timeout = '30s';`.
4. Add constraints (`CHECK`, `FOREIGN KEY`) with `NOT VALID` followed by `VALIDATE CONSTRAINT` in a non-blocking step.
5. Verify twice on an isolated AMP Postgres zero-copy branch (`amp_branch_create` -> temporary `ingress_external` compute scoped strictly to operator IPv4 `/32` CIDR -> idempotent re-run -> retire compute).

## 3. Webhook Delivery & Verification Contract

1. Signature Header: `X-Ledger-Signature: v1=<64-char-lowercase-hex-hmac-sha256>`.
2. Timestamp Header: `X-Ledger-Timestamp: <unix_epoch_seconds>`.
3. Canonical Signing String: `f"{timestamp}.{raw_body_utf8}"` computed strictly over exact raw request bytes (`ADR-003.2`), never parsed/dumped JSON.
4. Comparison: constant-time `hmac.compare_digest` (`ADR-003.1`) plus symmetric drift rejection `abs(now - ts) > 300` (`ADR-003.3`).

## 4. Telemetry, PII Redaction, and Error Envelope Contract

1. Runtime logs emit structured single-line JSON records containing `timestamp`, `level`, `event`, `tenant_id`, `correlation_id`, and sanitized `fields`.
2. Secret values (`token`, `secret`, `api_key`, `password`, `authorization`, `email`, `phone`, `ssn`, `tax_id`) become `"***REDACTED***"`; account numbers (`iban`, `account_number`, `card_number`) mask via `mask_last4()`.
3. HTTP failures return RFC 9457 JSON (`type`, `title`, `status`, `detail`, `trace_id`) with zero raw SQL or internal tracebacks.

## 5. Multi-Tenant SQL & RBAC Checklist

1. Repository methods require verified `AuthContext(actor_id, tenant_id, scopes)` and raise `TenantMismatchError` if client payload `tenant_id` disagrees with `auth_ctx.tenant_id`.
2. Allowed runtime scopes: `ledger:read`, `ledger:write`, `webhook:admin`, `migration:approve`. Wildcards (`*`) and silent role fallbacks are prohibited.
3. Parameterize all SQL queries with `%s` tuple parameters and explicit `WHERE tenant_id = %s` scoping.
