"""Unit tests for target_repo ledger-service invariants."""

from decimal import Decimal
import hashlib
import hmac
import pytest

from ledger_service.errors import (
    CircuitOpenError,
    IdempotencyConflictError,
    InvalidSignatureError,
    PermissionDeniedError,
    TenantMismatchError,
    UnbalancedJournalError,
    ValidationError,
    WebhookTimestampError,
)
from ledger_service.ledger import InMemoryLedgerStore, PostingLine, compute_fee_minor
from ledger_service.logging_utils import build_log_record, redact_payload
from ledger_service.retry_client import CircuitBreaker, HttpResult, execute_with_retry
from ledger_service.security import AuthContext, build_select_journal_query, enforce_tenant_match, require_scope
from ledger_service.webhook import verify_webhook_signature


def test_fee_round_half_even_without_float() -> None:
    assert compute_fee_minor(1000, Decimal("25")) == 2
    assert compute_fee_minor(1000, "35") == 4
    assert compute_fee_minor(1000, "25") == 2
    with pytest.raises(ValidationError):
        compute_fee_minor(1000, 0.25)  # type: ignore[arg-type]


def test_double_entry_and_idempotency() -> None:
    store = InMemoryLedgerStore()
    lines = [
        PostingLine(account_id="acct_a", direction="DEBIT", amount_minor=5000),
        PostingLine(account_id="acct_b", direction="CREDIT", amount_minor=5000),
    ]
    e1, replayed1 = store.post_journal("t1", "idem-1", "USD", lines)
    e2, replayed2 = store.post_journal("t1", "idem-1", "USD", lines)
    assert not replayed1 and replayed2
    assert e1.entry_id == e2.entry_id

    with pytest.raises(IdempotencyConflictError):
        store.post_journal(
            "t1",
            "idem-1",
            "USD",
            [
                PostingLine(account_id="acct_a", direction="DEBIT", amount_minor=6000),
                PostingLine(account_id="acct_b", direction="CREDIT", amount_minor=6000),
            ],
        )

    with pytest.raises(UnbalancedJournalError):
        store.post_journal(
            "t1",
            "idem-2",
            "USD",
            [
                PostingLine(account_id="acct_a", direction="DEBIT", amount_minor=5000),
                PostingLine(account_id="acct_b", direction="CREDIT", amount_minor=4900),
            ],
        )


def test_webhook_hmac_and_replay_window() -> None:
    secret = "whsec_test_key"
    ts = "1795000000"
    raw_body = b'{"event":"settled","b":2,"a":1}'
    digest = hmac.new(secret.encode(), f"{ts}.{raw_body.decode()}".encode(), hashlib.sha256).hexdigest()
    assert verify_webhook_signature(secret, ts, f"v1={digest}", raw_body, now_epoch=1795000100)

    with pytest.raises(WebhookTimestampError):
        verify_webhook_signature(secret, ts, f"v1={digest}", raw_body, now_epoch=1795000400)
    with pytest.raises(WebhookTimestampError):
        verify_webhook_signature(secret, ts, f"v1={digest}", raw_body, now_epoch=1794999500)
    with pytest.raises(InvalidSignatureError):
        verify_webhook_signature(secret, ts, "v1=" + "0" * 64, raw_body, now_epoch=1795000050)


def test_pii_redaction_nested() -> None:
    rec = build_log_record(
        "transfer_created",
        "t1",
        "corr-1",
        fields={"email": "a@b.com", "headers": {"Authorization": "Bearer abc"}, "iban": "DE89370400440532013000"},
    )
    assert rec["fields"]["email"] == "***REDACTED***"
    assert rec["fields"]["headers"]["Authorization"] == "***REDACTED***"
    assert rec["fields"]["iban"] == "****3000"
    assert redact_payload({"nested": [{"api_key": "secret123"}]})["nested"][0]["api_key"] == "***REDACTED***"


def test_retry_client_and_circuit_breaker() -> None:
    breaker = CircuitBreaker(failure_threshold=2, cooldown_seconds=30.0)
    calls = 0

    def flaky(timeouts: tuple[float, float]) -> HttpResult:
        nonlocal calls
        assert timeouts == (2.0, 5.0)
        calls += 1
        return HttpResult(status_code=503 if calls < 2 else 200, body="ok")

    res = execute_with_retry(flaky, breaker, max_attempts=3, sleep_fn=lambda _: None)
    assert res.status_code == 200 and calls == 2

    bad_calls = 0
    def client_err(_timeouts: tuple[float, float]) -> HttpResult:
        nonlocal bad_calls
        bad_calls += 1
        return HttpResult(status_code=422, body="bad")

    res422 = execute_with_retry(client_err, breaker, max_attempts=3, sleep_fn=lambda _: None)
    assert res422.status_code == 422 and bad_calls == 1

    breaker.record_failure()
    breaker.record_failure()
    with pytest.raises(CircuitOpenError):
        execute_with_retry(flaky, breaker, max_attempts=3, sleep_fn=lambda _: None)


def test_rbac_and_tenant_isolation() -> None:
    ctx = AuthContext(actor_id="u1", tenant_id="tenant_alpha", scopes=frozenset({"ledger:read"}))
    require_scope(ctx, "ledger:read")
    with pytest.raises(PermissionDeniedError):
        require_scope(ctx, "ledger:write")
    with pytest.raises(PermissionDeniedError):
        require_scope(AuthContext("u2", "tenant_alpha", frozenset({"*"})), "ledger:read")
    with pytest.raises(TenantMismatchError):
        enforce_tenant_match(ctx, "tenant_beta")
    sql, params = build_select_journal_query(ctx, "je_000001")
    assert "WHERE tenant_id = %s" in sql and params == ("tenant_alpha", "je_000001")
