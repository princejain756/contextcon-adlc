# INC-2026-078: Float Penny Drift and Partner Webhook Verification Failures

- Namespace: `adlc/proj/contextcon-adlc/postmortems`
- Date: 2026-10-08
- Severity: SEV-2 (Reconciliation mismatch + 4% webhook drop rate)

## Summary

A fee calculation refactor introduced `fee = round(gross * 0.0175, 2)` in float arithmetic, drifting by 2 cents per 10,000 settlements against clearing bank totals. In the same release, a webhook handler re-serialized parsed JSON via `json.dumps(payload)` before computing HMAC-SHA256, breaking signatures for partners whose keys were unsorted.

## Root Cause

1. Two separate coding assistants updated fee logic and webhook middleware in separate sessions without reading team ADRs (`ADR-002` and `ADR-003`).
2. Existing unit tests mocked HMAC signatures and used trivial round numbers like `100.0` that masked floating-point precision loss.

## Permanent Safeguards

1. Ban Python `float` types and float literals inside `ledger_service/ledger.py`, `fees.py`, and `refunds.py`; require `Decimal` with `ROUND_HALF_EVEN` rounding into integer minor units (`amount_minor: int`).
2. Mandate raw byte payload verification (`raw_body`) with `hmac.compare_digest` and symmetric `abs(now - ts) <= 300` replay window (`ADR-003`).
3. Log audit reasoning in Meko (`conversation_add_message`) citing exact ADR identifiers whenever fee, rounding, or signature logic changes.
