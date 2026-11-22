"""RBAC authorization and multi-tenant isolation guards conforming to ADR-006."""

from __future__ import annotations

from dataclasses import dataclass

from ledger_service.errors import PermissionDeniedError, TenantMismatchError

ALLOWED_SCOPES = frozenset({"ledger:read", "ledger:write", "webhook:admin", "migration:approve"})


@dataclass(frozen=True)
class AuthContext:
    actor_id: str
    tenant_id: str
    scopes: frozenset[str]


def require_scope(auth_ctx: AuthContext, required_scope: str) -> None:
    if required_scope not in ALLOWED_SCOPES:
        raise PermissionDeniedError(f"Unknown scope: {required_scope}")
    if required_scope not in auth_ctx.scopes:
        raise PermissionDeniedError(f"Actor {auth_ctx.actor_id} lacks required scope {required_scope}")


def enforce_tenant_match(auth_ctx: AuthContext, requested_tenant_id: str | None) -> str:
    if not auth_ctx.tenant_id or not auth_ctx.tenant_id.strip():
        raise TenantMismatchError("Missing authenticated tenant_id")
    if requested_tenant_id is not None and requested_tenant_id.strip() != auth_ctx.tenant_id.strip():
        raise TenantMismatchError("Request tenant_id does not match authenticated context")
    return auth_ctx.tenant_id.strip()


def build_select_journal_query(auth_ctx: AuthContext, entry_id: str) -> tuple[str, tuple[str, str]]:
    require_scope(auth_ctx, "ledger:read")
    sql = (
        "SELECT entry_id, tenant_id, idempotency_key, currency, created_at "
        "FROM journal_entries WHERE tenant_id = %s AND entry_id = %s;"
    )
    return sql, (auth_ctx.tenant_id.strip(), entry_id)
