"""Typed domain and HTTP problem errors per ADR-002, ADR-003, ADR-004, and ADR-006."""


class LedgerError(Exception):
    """Base error with RFC 9457 metadata."""

    status_code: int = 400
    error_type: str = "https://ledger.example/errors/domain"
    title: str = "Ledger Domain Error"


class ValidationError(LedgerError):
    status_code = 422
    error_type = "https://ledger.example/errors/validation"
    title = "Validation Error"


class IdempotencyConflictError(LedgerError):
    status_code = 409
    error_type = "https://ledger.example/errors/idempotency-conflict"
    title = "Idempotency Conflict"


class UnbalancedJournalError(LedgerError):
    status_code = 422
    error_type = "https://ledger.example/errors/unbalanced-journal"
    title = "Unbalanced Journal Entry"


class InvalidSignatureError(LedgerError):
    status_code = 401
    error_type = "https://ledger.example/errors/invalid-signature"
    title = "Invalid Webhook Signature"


class WebhookTimestampError(LedgerError):
    status_code = 401
    error_type = "https://ledger.example/errors/webhook-timestamp"
    title = "Webhook Replay Window Exceeded"


class PermissionDeniedError(LedgerError):
    status_code = 403
    error_type = "https://ledger.example/errors/forbidden"
    title = "Permission Denied"


class TenantMismatchError(LedgerError):
    status_code = 403
    error_type = "https://ledger.example/errors/tenant-mismatch"
    title = "Tenant Isolation Violation"


class CircuitOpenError(LedgerError):
    status_code = 503
    error_type = "https://ledger.example/errors/circuit-open"
    title = "Downstream Circuit Breaker Open"
