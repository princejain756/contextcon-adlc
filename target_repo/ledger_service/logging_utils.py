"""Structured JSON logging and PII redaction conforming to ADR-004."""

from __future__ import annotations

import json
import time
from typing import Any

SENSITIVE_EXACT_OR_SUBSTR = (
    "token",
    "secret",
    "api_key",
    "apikey",
    "password",
    "passwd",
    "authorization",
    "iban",
    "account_number",
    "card_number",
    "tax_id",
    "ssn",
    "email",
    "phone",
)

PARTIAL_MASK_KEYS = ("iban", "account_number", "card_number")


def mask_last4(value: str) -> str:
    cleaned = str(value).strip()
    if len(cleaned) <= 4:
        return "****"
    return "****" + cleaned[-4:]


def _is_sensitive_key(key: str) -> bool:
    low = key.lower().strip()
    return any(tok in low for tok in SENSITIVE_EXACT_OR_SUBSTR)


def redact_payload(value: Any) -> Any:
    """Recursively mask sensitive fields in nested dicts, lists, and tuples."""
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            ks = str(k)
            low = ks.lower().strip()
            if _is_sensitive_key(ks) and not isinstance(v, (dict, list, tuple)):
                if any(pm in low for pm in PARTIAL_MASK_KEYS):
                    out[ks] = mask_last4("" if v is None else str(v))
                else:
                    out[ks] = "***REDACTED***"
            else:
                out[ks] = redact_payload(v)
        return out
    if isinstance(value, list):
        return [redact_payload(item) for item in value]
    if isinstance(value, tuple):
        return [redact_payload(item) for item in value]
    return value


def build_log_record(
    event: str,
    tenant_id: str,
    correlation_id: str,
    level: str = "INFO",
    fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "timestamp": int(time.time()),
        "level": level.upper(),
        "event": event,
        "tenant_id": tenant_id,
        "correlation_id": correlation_id,
        "fields": redact_payload(fields or {}),
    }


def serialize_log_record(
    event: str,
    tenant_id: str,
    correlation_id: str,
    level: str = "INFO",
    fields: dict[str, Any] | None = None,
) -> str:
    return json.dumps(
        build_log_record(event, tenant_id, correlation_id, level=level, fields=fields),
        sort_keys=True,
        separators=(",", ":"),
    )


def build_problem_detail(
    status: int,
    title: str,
    detail: str,
    trace_id: str,
    error_type: str = "https://ledger.example/errors/domain",
    extras: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "type": error_type,
        "title": title,
        "status": int(status),
        "detail": detail,
        "trace_id": trace_id,
    }
    if extras:
        body["extensions"] = redact_payload(extras)
    return body
