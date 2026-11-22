# ADR-003: Webhook HMAC Verification and Replay Protection

- Status: Accepted
- Namespace: `adlc/proj/contextcon-adlc/adrs`
- Applies To: `target_repo/ledger_service/webhook.py`

## Context

Partner settlement callbacks deliver asynchronous state changes over public HTTP endpoints. Naive JSON re-serialization or direct string equality exposes signature forging and replay attacks.

## Mandatory Rules

1. **Rule ADR-003.1 (Constant-Time Signature Comparison)**:
   - Always verify HMAC-SHA256 digests with `hmac.compare_digest(expected_hex, received_hex)`.
   - Never compare signature strings or digests with `==`, `!=`, or set membership.
2. **Rule ADR-003.2 (Raw Body Byte Signing Only)**:
   - Never parse JSON and call `json.dumps(payload)` to construct the signed string. Formatting differences (key sorting, unicode escaping, whitespace) break partner signatures or create ambiguity bugs.
   - Sign strictly over `f"{timestamp}.{raw_body.decode('utf-8')}"` encoded as UTF-8 bytes (after stripping `"v1="` prefix cleanly from `X-Ledger-Signature`).
3. **Rule ADR-003.3 (Bounded Replay Window)**:
   - Require `X-Ledger-Timestamp` (Unix seconds integer). Parse strictly inside explicit validation returning `InvalidSignatureError` / `WebhookTimestampError` on malformed input.
   - Reject any event where `abs(current_epoch_seconds - timestamp_seconds) > 300` (`MAX_WEBHOOK_DRIFT_SECONDS = 300`). Both stale past events and far-future timestamps fail fast.
4. **Rule ADR-003.4 (Secret Hygiene)**:
   - Webhook signing secrets are supplied per tenant or caller argument from secure env/secret managers (`os.environ`), never hardcoded fallback literals such as `"dev-secret"` or `"changeme"`.

## Anti-Patterns Rejected During PR Review

- `if computed_sig == provided_sig:` (timing leak).
- `payload_str = json.dumps(json.loads(raw_body))` before HMAC calculation.
- Checking `now - ts > 300` without `abs(...)`, allowing future timestamp bypasses.
