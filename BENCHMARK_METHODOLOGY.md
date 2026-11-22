# Benchmark Methodology & Full Results

## Experimental Setup

This benchmark compares full-repository prompt stuffing (**Baseline**) against **Meko Shared Context** retrieval (`context_search`) across 10 engineering tasks spanning SQL migrations, precision financial math, idempotency, webhook cryptography, PII redaction, retries, tenant-isolated SQL, and RBAC guards (`conversation_id: 4913e2414cd94d5ca6920bafd61c3da4`).

| Parameter | Setting |
| --- | --- |
| Target codebase | `target_repo/` (18 files: 9 standards docs, 7 Python modules, 2 SQL migrations) |
| Model CLI | `commandcode -p -m deepseek/deepseek-v4.1-flash --no-session --effort low` |
| Working directory | `/tmp` (isolated so the CLI does not read repo files off disk) |
| Tokenizer | OpenAI `cl100k_base` via `tiktoken` |
| Reference pricing | `$3.00 / 1M input tokens, $15.00 / 1M output tokens` (`1x` input, `5x` output) |
| Timeout & retry policy | `240.0s` subprocess timeout, up to `1` retry on `TimeoutExpired` |
| Baseline context | All 18 files concatenated (`9,359` tokens per prompt) |
| Meko context | `context_search(..., limit=6)`: top `6` KB chunks + top `3` memories, capped at `14,000` chars |

## Deterministic Verifiers (`src/meko_adlc/verifiers.py`)

Each model output is parsed from code fences and evaluated offline without LLM judging:

- `T01` (`sql_index`): Requires `-- migrate:no-transaction` / `NO_TX`, `SET lock_timeout = '2s'`, `SET statement_timeout = '30s'`, and `CREATE INDEX CONCURRENTLY` (rejects plain `CREATE INDEX`).
- `T02` (`fee_refund`): AST forbids `float` types/literals and builtin `round()`; requires `Decimal` + `ROUND_HALF_EVEN`, `idempotency_key`, refund cap check, and executes `fn(1000, Decimal("25")) == 2` and `fn(1000, Decimal("35")) == 4`.
- `T03` (`double_entry`): AST check (no floats, no `print`) + `sha256`, `DEBIT`/`CREDIT`, `idempotency_key`, and balance equality check.
- `T04` (`webhook`): Requires `hmac.compare_digest`, forbids `json.dumps` and `==` signature comparisons, requires `v1=` prefix handling and `abs(...)` `300`s replay check.
- `T05` (`pii_redactor`): Requires `***REDACTED***`, `****` last-4 masking, RFC 9457 keys (`trace_id`, `status`, `title`, `detail`), no `print()`, plus runtime nested redaction assertion.
- `T06` (`retry_breaker`): Forbids `while True:`, requires `random` jitter, retryable `408/429/502/503/504`, non-retryable 4xx exclusion, and `CircuitBreaker` `OPEN` state + timeouts.
- `T07` (`tenant_sql`): AST SQL-injection check forbidding f-strings/`%`/`+`/`.format()`, requires `tenant_id = %s`, `AuthContext`, and tenant mismatch guard.
- `T08` (`rbac_guard`): Requires exact scopes (`ledger:read`, `ledger:write`, `webhook:admin`, `migration:approve`) and rejects `*` wildcard or implicit `admin` role fallback.
- `T09` (`sql_constraint`): Requires lock/statement timeouts, two-phase `NOT VALID` + `VALIDATE CONSTRAINT`, and forbids `SERIAL`/`BIGSERIAL`.
- `T10` (`composite_refund`): Composite AST + symbol check requiring `Decimal` + `ROUND_HALF_EVEN`, `idempotency_key`, `ledger:write`, PII redaction (`redact` or `***REDACTED***`), `tenant_id`, and safe SQL.

## Full 10-Task Paired Measurements

| Task | Title | Base In | Meko In | Base Tot | Meko Tot | Tot Saved | Base Cost | Meko Cost | Base Time | Meko Time | Base Pass | Meko Pass |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| T01 | Zero-Downtime Lookup Index Migration | 9,421 | 1,009 | 9,526 | 1,059 | 88.9% | $0.029838 | $0.003777 | 15.03s | 10.80s (search 4.88s) | PASS (0) | PASS (0) |
| T02 | Fee Calculator & Cumulative Refund Cap | 9,455 | 1,194 | 10,359 | 2,992 | 71.1% | $0.041925 | $0.030552 | 23.83s | 44.69s (search 5.22s) | PASS (0) | PASS (0) |
| T03 | Double-Entry Transfer & Request Fingerprint | 9,439 | 794 | 11,145 | 4,342 | 61.0% | $0.053907 | $0.055602 | 55.12s | 105.43s (search 3.33s) | PASS (0) | PASS (0) |
| T04 | Webhook HMAC Signature & Replay Window | 9,436 | 881 | 10,011 | 1,379 | 86.2% | $0.036933 | $0.010113 | 12.96s | 26.13s (search 4.84s) | PASS (0) | PASS (0) |
| T05 | Nested PII Redaction & RFC 9457 Error Builder | 9,453 | 697 | 10,535 | 1,765 | 83.2% | $0.044589 | $0.018111 | 23.85s | 63.30s (search 2.83s) | PASS (0) | PASS (0) |
| T06 | Bounded Jittered Retry Client & Circuit Breaker | 9,441 | 861 | 10,624 | 3,441 | 67.6% | $0.046068 | $0.041283 | 16.43s | 121.69s (search 5.14s) | PASS (0) | PASS (0) |
| T07 | Tenant-Isolated Parameterized SQL Queries | 9,442 | 647 | 10,357 | 1,418 | 86.3% | $0.042051 | $0.013506 | 16.38s | 30.91s (search 2.78s) | PASS (0) | PASS (0) |
| T08 | Default-Deny Exact RBAC Scope Guard | 9,427 | 593 | 10,045 | 1,002 | 90.0% | $0.037551 | $0.007914 | 16.38s | 15.99s (search 3.06s) | PASS (0) | PASS (0) |
| T09 | Two-Phase CHECK Constraint Migration | 9,437 | 1,109 | 9,659 | 1,584 | 83.6% | $0.031641 | $0.010452 | 9.72s | 44.96s (search 3.48s) | PASS (0) | PASS (0) |
| T10 | Cross-ADR Tenant Refund Command Handler | 9,466 | 1,240 | 10,570 | 3,960 | 62.5% | $0.044958 | $0.044520 | 68.48s | 55.93s (search 4.41s) | FAIL (2) | PASS (0) |
| **ALL** | **10-Task Aggregate** | **94,417** | **9,025** | **102,831** | **22,942** | **77.69%** | **$0.409461** | **$0.235830** | **258.19s** | **519.83s (search 39.97s)** | **9/10** | **10/10** |

## Honest Analysis, Failures, and Tradeoffs

1. **Why Baseline Failed `T10` (`2` Violations)**:
   Task `T10` asked for a self-contained `handle_refund_command(...)` function combining ADRs 002, 004, and 006. Seeing all `ledger_service` files in full-repo context, Baseline imported `compute_fee_minor` from `ledger_service.ledger` and `build_log_record` from `ledger_service.logging_utils` rather than implementing self-contained rounding and redaction logic directly, triggering verifier flags `ADR-002.1` (missing `ROUND_HALF_EVEN` in module text) and `ADR-004.1` (missing inline `redact` / `***REDACTED***`). Focused retrieval in the Meko arm kept prompt context on the self-contained requirements and passed `10/10`.
2. **Corpus Symmetry Discovery on Pre-Fix Run (`T02`)**:
   In an earlier run before indexing `target_repo` Python/SQL files alongside ADRs, Baseline passed `T02` (`Decimal | str | int` copied from `ledger.py`) while Meko saw only `ADR-002` and typed `rate_bps: int`, failing when the verifier passed `Decimal("25")`. Adding `target_repo` source modules and migrations to Meko KB as `.txt` files resolved the asymmetry without editing any verifier or prompt (`T02` passed on both arms afterward).
3. **Completion Token Expansion vs Prompt Compression**:
   Under `$3/1M` input and `$15/1M` output pricing, Meko cut prompt tokens by **90.44%** (`94,417` down to `9,025`), while Meko completion output rose from `8,414` to `13,917` tokens (agents writing fuller defensive dataclasses and guards). Total tokens still dropped **77.69%** (`102,831` down to `22,942`) and reference cost dropped **42.40%** (`$0.409461` down to `$0.235830`). On `T03` specifically, higher completion volume (`3,548` vs `1,706` output tokens) made Meko slightly more expensive (`$0.055602` vs `$0.053907`) even though total tokens fell `61.0%`.
4. **Wall Latency Accounting (Completed-Attempt +101.34% vs Retry-Inclusive Lower Bound +194.30%)**:
   Completed-attempt wall time averaged `51.983s` per task in Meko (`519.832s` total: `39.97s` across 10 `context_search` calls plus `479.86s` LLM inference) vs `25.819s` (`258.187s` total) in Baseline (+101.34%). Because `T10` in the Meko arm timed out once at `240.0s` before completing in `55.929s` on retry, adding that documented `240.0s` failed attempt yields a minimum retry-inclusive Meko total of `759.832s` (`75.983s` average per task, `+194.30%` vs Baseline). `_run_cli_with_retry()` now records both completed-attempt and retry-inclusive end-to-end monotonic durations automatically. In this 18-file (`9,359`-token) benchmark repo, full-repo context still fit inside one prompt window; on larger multi-service repositories, full-repo stuffing hits fixed context limits while our observed `context_search` prompts stayed between `593` and `1,240` `cl100k_base` tokens.
5. **Single-Run Scope**:
   Measurements reflect one deterministic run on `deepseek/deepseek-v4.1-flash` (`--effort low`) over the synthetic `target_repo/` benchmark codebase. Re-running is repeatable via `uv run meko-adlc benchmark --limit 6 --timeout 240`.
