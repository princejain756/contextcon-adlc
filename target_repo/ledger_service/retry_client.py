"""Bounded exponential retry client + circuit breaker conforming to ADR-005."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Callable, TypeVar

from ledger_service.errors import CircuitOpenError

T = TypeVar("T")

RETRYABLE_HTTP_STATUSES = frozenset({408, 429, 502, 503, 504})
NON_RETRYABLE_HTTP_STATUSES = frozenset({400, 401, 403, 404, 409, 422})
DEFAULT_MAX_ATTEMPTS = 3
BASE_DELAY_MS = 100
MAX_DELAY_MS = 2000
MAX_RETRY_AFTER_S = 10.0
DEFAULT_TIMEOUTS = (2.0, 5.0)


@dataclass(frozen=True)
class HttpResult:
    status_code: int
    body: str
    retry_after: float | None = None


class CircuitBreaker:
    """Explicit state breaker for downstream payment calls."""

    def __init__(self, failure_threshold: int = 5, cooldown_seconds: float = 30.0) -> None:
        self.failure_threshold = min(max(1, failure_threshold), 10)
        self.cooldown_seconds = cooldown_seconds
        self.consecutive_failures = 0
        self.opened_at: float | None = None

    def state(self, now: float | None = None) -> str:
        if self.opened_at is None:
            return "CLOSED"
        ts = time.monotonic() if now is None else now
        if ts - self.opened_at >= self.cooldown_seconds:
            return "HALF_OPEN"
        return "OPEN"

    def ensure_closed(self, now: float | None = None) -> None:
        if self.state(now=now) == "OPEN":
            raise CircuitOpenError("Downstream circuit breaker is open")

    def record_success(self) -> None:
        self.consecutive_failures = 0
        self.opened_at = None

    def record_failure(self, now: float | None = None) -> None:
        self.consecutive_failures += 1
        if self.consecutive_failures >= self.failure_threshold:
            self.opened_at = time.monotonic() if now is None else now


def compute_backoff_seconds(
    attempt_index: int,
    base_delay_ms: int = BASE_DELAY_MS,
    max_delay_ms: int = MAX_DELAY_MS,
    retry_after: float | None = None,
    rng: Callable[[float, float], float] = random.uniform,
) -> float:
    if retry_after is not None and retry_after > 0:
        return min(float(retry_after), MAX_RETRY_AFTER_S)
    capped_ms = min(max_delay_ms, base_delay_ms * (2 ** max(0, attempt_index - 1)))
    jittered_ms = capped_ms * rng(0.5, 1.0)
    return jittered_ms / 1000.0


def execute_with_retry(
    fn: Callable[[tuple[float, float]], HttpResult],
    breaker: CircuitBreaker,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> HttpResult:
    attempts = min(max(1, max_attempts), 4)
    last_exc: Exception | None = None

    for attempt in range(1, attempts + 1):
        breaker.ensure_closed()
        try:
            res = fn(DEFAULT_TIMEOUTS)
        except TimeoutError as exc:
            last_exc = exc
            breaker.record_failure()
            if attempt >= attempts:
                raise
            sleep_fn(compute_backoff_seconds(attempt))
            continue

        if 200 <= res.status_code < 300:
            breaker.record_success()
            return res

        if res.status_code in NON_RETRYABLE_HTTP_STATUSES or res.status_code not in RETRYABLE_HTTP_STATUSES:
            return res

        breaker.record_failure()
        if attempt >= attempts:
            return res
        sleep_fn(compute_backoff_seconds(attempt, retry_after=res.retry_after))

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("Retry loop terminated unexpectedly")
