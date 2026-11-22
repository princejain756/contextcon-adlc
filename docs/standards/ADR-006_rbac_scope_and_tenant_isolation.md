# ADR-006: RBAC Scopes and Strict Multi-Tenant Data Isolation

- Status: Accepted
- Namespace: `adlc/proj/contextcon-adlc/adrs`
- Applies To: `target_repo/ledger_service/security.py`, `target_repo/ledger_service/repository.py`

## Context

Cross-tenant query leaks or permissive RBAC defaults cause critical security breaches in shared B2B payment platforms. Authorization and tenant scoping must be verified explicitly at both application and SQL query boundaries.

## Mandatory Rules

1. **Rule ADR-006.1 (Explicit Tenant Context Over Request Payload)**:
   - Every repository read or write method accepts `auth_ctx: AuthContext` containing verified `tenant_id` and granted `scopes: frozenset[str]`.
   - Never trust a tenant ID supplied inside a JSON request body over `auth_ctx.tenant_id`. Raise `TenantMismatchError` if both are present and differ.
2. **Rule ADR-006.2 (Default-Deny Exact Scope Checks)**:
   - Valid system scopes are restricted to `{"ledger:read", "ledger:write", "webhook:admin", "migration:approve"}`.
   - Guard functions (`require_scope(auth_ctx, required_scope)`) deny by default (`PermissionDeniedError`) whenever `required_scope` is absent or empty. Wildcard `"*"` or role fallbacks are strictly forbidden in runtime enforcement.
3. **Rule ADR-006.3 (Parameterized SQL Queries Only)**:
   - All SQL query builders must return `(query_str, params_tuple)` using `%s` placeholders.
   - Never assemble SQL strings with Python f-strings, `.format()`, `%` operator interpolation, or `+` string concatenation.
   - Read and mutation SQL strings on tenant-owned tables (`accounts`, `journal_entries`, `journal_lines`, `webhook_endpoints`) must explicitly bind `tenant_id = %s` in the `WHERE` predicate.

## Anti-Patterns Rejected During PR Review

- `sql = f"SELECT * FROM accounts WHERE id = '{account_id}'"` (SQL injection + missing `WHERE tenant_id = %s`).
- Checking `if "admin" in user_roles or required_scope in scopes` or accepting `"*"` scope bypasses.
