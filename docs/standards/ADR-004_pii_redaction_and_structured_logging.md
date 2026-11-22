# ADR-004: PII Redaction and Structured JSON Logging

- Status: Accepted
- Namespace: `adlc/proj/contextcon-adlc/adrs`
- Applies To: `target_repo/ledger_service/logging_utils.py`, API handlers, background workers

## Context

Financial service logs flow to centralized collectors and audit dashboards. Unmasked PII, raw bearer tokens, or ad-hoc `print()` strings violate data governance and make automated log parsing brittle.

## Mandatory Rules

1. **Rule ADR-004.1 (Mandatory Field Redaction)**:
   - Any dictionary serialized for logs or error telemetry must pass recursively through `redact_payload(data)` before emission.
   - Sensitive key names matching `token`, `secret`, `api_key`, `password`, `authorization`, `iban`, `account_number`, `card_number`, `ssn`, `tax_id`, `email`, or `phone` (case-insensitive substring or exact match) must be replaced cleanly: secrets become `"***REDACTED***"`, while bank account identifiers (`iban`, `account_number`, `card_number`) may preserve at most the trailing 4 characters via `mask_last4()` (`"****1234"`) or `"***REDACTED***"`.
2. **Rule ADR-004.2 (Structured JSON Only, Zero Raw print)**:
   - Never call bare `print(...)` inside `ledger_service/` runtime modules or interpolate untrusted values into f-string log lines (`logger.info(f"user {email} ...")`).
   - Emit single-line JSON records via `build_log_record(event, tenant_id, correlation_id, level="INFO", fields=None)` containing `timestamp`, `level`, `event`, `tenant_id`, `correlation_id`, and redacted `fields`.
3. **Rule ADR-004.3 (RFC 9457 Error Responses Without Stack Leaks)**:
   - Public error builders (`build_problem_detail`) emit RFC 9457 fields (`type`, `title`, `status`, `detail`, `trace_id`) and redact sensitive strings before serialization. Never include raw SQL strings, credentials, or internal tracebacks in HTTP `detail`.

## Anti-Patterns Rejected During PR Review

- `print("Debug token:", token)` or `logger.info(f"Webhook verified for {email}")`.
- Flat redaction checking only top-level dict keys while skipping nested `headers`, `metadata`, or `list` items.
