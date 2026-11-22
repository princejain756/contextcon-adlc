# ADR-005: Bounded Exponential Retry and Circuit Breakers

- Status: Accepted
- Namespace: `adlc/proj/contextcon-adlc/adrs`
- Applies To: `target_repo/ledger_service/retry_client.py`

## Context

Downstream bank rails and settlement gateways experience brief brownouts. Infinite retry loops or un-jittered retries synchronize traffic spikes ("thundering herd") and exhaust worker threads.

## Mandatory Rules

1. **Rule ADR-005.1 (Hard Attempt Cap and Jittered Backoff)**:
   - Never write `while True:` retry loops or unbounded retry counts.
   - Default and enforce `max_attempts <= 4` (`DEFAULT_MAX_ATTEMPTS = 3`), `base_delay_ms = 100`, `max_delay_ms = 2000`.
   - Backoff delay on attempt `k` (1-indexed) must multiply `min(max_delay_ms, base_delay_ms * (2 ** (k - 1)))` by jitter `random.uniform(0.5, 1.0)` so concurrent callers spread evenly.
2. **Rule ADR-005.2 (Retryable Status Allowlist Only)**:
   - Retry strictly on transient network/timeout errors and HTTP status codes `{408, 429, 502, 503, 504}`.
   - Never retry client/auth/validation responses `{400, 401, 403, 404, 409, 422}`; fail immediately.
   - When receiving HTTP `429` with numeric `Retry-After`, cap wait at `MAX_RETRY_AFTER_SECONDS = 10.0`.
3. **Rule ADR-005.3 (Explicit Timeouts and Circuit Breaker Gate)**:
   - Outbound transport configuration must specify explicit finite timeouts (`DEFAULT_CONNECT_TIMEOUT_S = 2.0`, `DEFAULT_READ_TIMEOUT_S = 5.0`), never `timeout=None`.
   - `CircuitBreaker` tracks consecutive failures (`failure_threshold = 5`, `cooldown_seconds = 30.0`). When `state == "OPEN"` prior to cooldown expiry, fail fast with `CircuitOpenError` without invoking upstream calls or burning retries.

## Anti-Patterns Rejected During PR Review

- `requests.post(url, json=body)` without `timeout=` or retry loop calling `time.sleep(2 ** attempt)` without jitter.
- Retrying HTTP `400` / `422` validation errors 5 times.
