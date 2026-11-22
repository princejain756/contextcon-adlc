"""Webhook signature and replay verification conforming to ADR-003."""

from __future__ import annotations

import hashlib
import hmac
import time

from ledger_service.errors import InvalidSignatureError, WebhookTimestampError

MAX_WEBHOOK_DRIFT_SECONDS = 300


def verify_webhook_signature(
    secret: str,
    timestamp_header: str,
    signature_header: str,
    raw_body: bytes,
    now_epoch: int | None = None,
) -> bool:
    if not secret:
        raise InvalidSignatureError("Webhook signing secret is required")
    if not isinstance(raw_body, (bytes, bytearray)):
        raise InvalidSignatureError("raw_body must be bytes")
    if not signature_header or not signature_header.startswith("v1="):
        raise InvalidSignatureError("Signature header missing v1= prefix")

    try:
        ts_val = int(str(timestamp_header).strip())
    except (TypeError, ValueError) as exc:
        raise WebhookTimestampError("Invalid timestamp header") from exc

    current = int(time.time()) if now_epoch is None else int(now_epoch)
    if abs(current - ts_val) > MAX_WEBHOOK_DRIFT_SECONDS:
        raise WebhookTimestampError("Webhook timestamp outside 300s replay window")

    provided_hex = signature_header[3:].strip().lower()
    if len(provided_hex) != 64:
        raise InvalidSignatureError("Malformed hex digest length")

    signed_payload = f"{ts_val}.{bytes(raw_body).decode('utf-8')}".encode("utf-8")
    expected_hex = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected_hex, provided_hex):
        raise InvalidSignatureError("Webhook HMAC mismatch")
    return True
