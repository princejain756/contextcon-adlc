# ADR-002: Ledger Idempotency and Financial Precision

- Status: Accepted
- Namespace: `adlc/proj/contextcon-adlc/adrs`
- Applies To: `target_repo/ledger_service/ledger.py`, `target_repo/ledger_service/refunds.py`, `target_repo/sql/`

## Context

Floating-point rounding drift and duplicate retry submissions silently corrupt financial ledgers. Every money movement in `ledger-service` must remain deterministic, balanced, and strictly idempotent under retries.

## Mandatory Rules

1. **Rule ADR-002.1 (Zero Binary Floats for Currency)**:
   - Never represent currency amounts, fees, tax rates, or balances using Python `float` or SQL `FLOAT`, `REAL`, or `DOUBLE PRECISION`.
   - Store and calculate ledger amounts in integer minor units (`amount_minor: int`, Postgres `BIGINT` or `NUMERIC(20, 0)`), and use `decimal.Decimal` with `decimal.ROUND_HALF_EVEN` (banker's rounding) whenever computing fractional fee or FX conversions before converting back to `int` minor units.
2. **Rule ADR-002.2 (Strict Double-Entry Conservation)**:
   - Every `JournalEntry` must carry at least 2 `PostingLine` entries with directions restricted exclusively to `"DEBIT"` or `"CREDIT"`.
   - Every line must satisfy `amount_minor > 0`.
   - Total debits must strictly equal total credits (`sum(debit lines) == sum(credit lines) > 0`). Reject single-sided or unbalanced postings before persistence.
3. **Rule ADR-002.3 (Mandatory Idempotency Key and Request Fingerprint)**:
   - Every mutating ledger operation (`post_journal`, `create_transfer`, `create_refund`) requires a non-empty `idempotency_key: str` (`<= 128` chars, stripped).
   - Compute canonical SHA-256 `request_hash` over `(tenant_id, operation, sorted lines / minor amounts, currency)`.
   - Persist uniqueness scoped by `(tenant_id, idempotency_key)`. Replaying the exact same `(tenant_id, idempotency_key, request_hash)` returns the existing recorded result with `replayed=True`; reusing the same key with a different `request_hash` must raise `IdempotencyConflictError`.
4. **Rule ADR-002.4 (Refund Cap and Conservation Guard)**:
   - Cumulative refunds against a source transfer may never exceed the original settled transfer `amount_minor`. Check remaining refundable balance inside the atomic transaction boundary before posting counter-entries.

## Anti-Patterns Rejected During PR Review

- `fee = amount * 0.029` (uses Python binary `float` literal `0.029`).
- `round(amount * rate, 2)` instead of `Decimal` + `quantize(..., rounding=ROUND_HALF_EVEN)`.
- Allowing `idempotency_key: str | None = None` that silently falls back to generating a fresh UUID on every retry.
