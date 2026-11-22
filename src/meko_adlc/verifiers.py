"""Deterministic AST, SQL, and behavioral verifiers for ADRs 001 through 006."""

from __future__ import annotations

import ast
import hashlib
import hmac
import json
import re
import subprocess
import sys
import time
from typing import Any


def strip_markdown_fences(raw_text: str) -> str:
    """Extract Python or SQL block cleanly if wrapped in markdown fences."""
    text = raw_text.strip()
    m = re.search(r"```(?:python|py|sql)?\s*\n(.*?)```", text, flags=re.S | re.I)
    if m:
        return m.group(1).strip()
    return text


def _check_python_ast_no_float(tree: ast.AST) -> list[str]:
    # Allow explicit defensive `if isinstance(..., float): raise ...` guards without permitting float arithmetic/types
    safe_guard_float_ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.If) and any(isinstance(stmt, ast.Raise) for stmt in node.body):
            for sub in ast.walk(node.test):
                if (
                    isinstance(sub, ast.Call)
                    and isinstance(sub.func, ast.Name)
                    and sub.func.id == "isinstance"
                    and len(sub.args) >= 2
                ):
                    for arg_sub in ast.walk(sub.args[1]):
                        if isinstance(arg_sub, ast.Name) and arg_sub.id == "float":
                            safe_guard_float_ids.add(id(arg_sub))

    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, float):
            violations.append(f"ADR-002.1: float literal {node.value!r} prohibited")
        elif isinstance(node, ast.Name) and node.id == "float" and id(node) not in safe_guard_float_ids:
            violations.append("ADR-002.1: `float` type/call prohibited")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "round":
            violations.append("ADR-002.1: builtin `round()` prohibited; use Decimal.quantize(..., rounding=ROUND_HALF_EVEN)")
    return sorted(set(violations))


def _check_python_ast_no_print(tree: ast.AST) -> list[str]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "print":
            return ["ADR-004.2: bare `print()` prohibited in ledger_service modules"]
    return []


def _check_sql_string_interpolation(tree: ast.AST) -> list[str]:
    sql_kw = re.compile(r"\b(SELECT|INSERT|UPDATE|DELETE)\b", re.I)
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            joined_const = " ".join(v.value for v in node.values if isinstance(v, ast.Constant) and isinstance(v.value, str))
            if sql_kw.search(joined_const):
                violations.append("ADR-006.3: f-string SQL interpolation prohibited")
        elif isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Mod, ast.Add)):
            for side in (node.left, node.right):
                if isinstance(side, ast.Constant) and isinstance(side.value, str) and sql_kw.search(side.value):
                    if "%s" not in side.value or isinstance(node.op, ast.Mod):
                        violations.append("ADR-006.3: dynamic SQL `%` or `+` concatenation prohibited")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "format":
            if isinstance(node.func.value, ast.Constant) and isinstance(node.func.value.value, str) and sql_kw.search(node.func.value.value):
                violations.append("ADR-006.3: `.format()` SQL interpolation prohibited")
    return sorted(set(violations))


def verify_sql_index_migration(code: str) -> dict[str, Any]:
    sql = strip_markdown_fences(code)
    low = sql.lower()
    v: list[str] = []
    if "migrate:no-transaction" not in low and "no_tx" not in low:
        v.append("ADR-001.1: missing `-- migrate:no-transaction` / NO_TX marker")
    if not re.search(r"set\s+lock_timeout\s*=\s*['\"]?2s", low):
        v.append("ADR-001.2: missing `SET lock_timeout = '2s';`")
    if not re.search(r"set\s+statement_timeout\s*=\s*['\"]?30s", low):
        v.append("ADR-001.2: missing `SET statement_timeout = '30s';`")
    if not re.search(r"create\s+index\s+concurrently", low):
        v.append("ADR-001.1: index creation must use `CREATE INDEX CONCURRENTLY`")
    elif re.search(r"create\s+index\s+(?!concurrently)", low):
        v.append("ADR-001.1: non-concurrent `CREATE INDEX` found")
    return {"passed": len(v) == 0, "rule_violations": v, "details": {"sql_len": len(sql)}}


def verify_sql_constraint_migration(code: str) -> dict[str, Any]:
    sql = strip_markdown_fences(code)
    low = sql.lower()
    v: list[str] = []
    if not re.search(r"set\s+lock_timeout\s*=\s*['\"]?2s", low):
        v.append("ADR-001.2: missing `SET lock_timeout = '2s';`")
    if not re.search(r"set\s+statement_timeout\s*=\s*['\"]?30s", low):
        v.append("ADR-001.2: missing `SET statement_timeout = '30s';`")
    if "not valid" not in low:
        v.append("ADR-001.3: constraint must be added with `NOT VALID` first")
    if "validate constraint" not in low:
        v.append("ADR-001.3: missing separate `VALIDATE CONSTRAINT` statement")
    if re.search(r"\b(bigserial|serial)\b", low):
        v.append("ADR-001.4: SERIAL / BIGSERIAL prohibited")
    return {"passed": len(v) == 0, "rule_violations": v, "details": {"sql_len": len(sql)}}



_DISALLOWED_RUNTIME_IMPORTS = frozenset({
    "os",
    "subprocess",
    "sys",
    "socket",
    "urllib",
    "http",
    "pathlib",
    "shutil",
    "ctypes",
    "importlib",
    "builtins",
    "io",
    "signal",
    "multiprocessing",
    "threading",
    "pickle",
})
_DISALLOWED_RUNTIME_CALLS = frozenset({
    "open",
    "eval",
    "exec",
    "__import__",
    "compile",
    "getattr",
    "setattr",
    "delattr",
    "globals",
    "locals",
})


def _check_python_ast_safe_for_runtime(tree: ast.AST) -> list[str]:
    """Reject dangerous stdlib imports or dynamic builtins before isolated runtime execution."""
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root in _DISALLOWED_RUNTIME_IMPORTS:
                    violations.append(f"SECURITY: disallowed import `{root}` in verified candidate")
        elif isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split(".", 1)[0]
            if root in _DISALLOWED_RUNTIME_IMPORTS:
                violations.append(f"SECURITY: disallowed import `{root}` in verified candidate")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in _DISALLOWED_RUNTIME_CALLS:
                violations.append(f"SECURITY: disallowed call `{node.func.id}()` in verified candidate")
    return sorted(set(violations))


def _run_isolated_runtime_check(src: str, harness_code: str, timeout_s: float = 3.0) -> list[str]:
    """Execute candidate Python + assertions inside an isolated `-I -S` child process (never in-process)."""
    runner = (
        "import json\n"
        "try:\n"
        "    import resource\n"
        "    resource.setrlimit(resource.RLIMIT_CPU, (2, 2))\n"
        "except Exception:\n"
        "    pass\n"
        f"src = {json.dumps(src)}\n"
        f"harness = {json.dumps(harness_code)}\n"
        "ns = {}\n"
        "exec(compile(src, '<candidate>', 'exec'), ns)\n"
        "exec(compile(harness, '<harness>', 'exec'), ns)\n"
    )
    try:
        proc = subprocess.run(
            [sys.executable, "-I", "-S", "-c", runner],
            env={},
            timeout=timeout_s,
            capture_output=True,
            text=True,
        )
    except subprocess.TimeoutExpired:
        return [f"RUNTIME: isolated verification timed out after {timeout_s}s"]
    except Exception as exc:
        return [f"RUNTIME: isolated runner failure: {type(exc).__name__}: {exc}"]

    if proc.returncode != 0:
        err_lines = [ln.strip() for ln in (proc.stderr or proc.stdout or "").splitlines() if ln.strip()]
        summary = err_lines[-1] if err_lines else f"exit={proc.returncode}"
        return [f"RUNTIME: {summary[:220]}"]
    return []


def verify_fee_and_refund_module(code: str) -> dict[str, Any]:
    src = strip_markdown_fences(code)
    v: list[str] = []
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        return {"passed": False, "rule_violations": [f"SYNTAX: {exc}"], "details": {}}

    v.extend(_check_python_ast_no_float(tree))
    v.extend(_check_python_ast_no_print(tree))
    if "Decimal" not in src or "ROUND_HALF_EVEN" not in src:
        v.append("ADR-002.1: must use Decimal with ROUND_HALF_EVEN")
    if not re.search(r"idempotency_key", src):
        v.append("ADR-002.3: idempotency_key parameter missing")
    if not re.search(r"(refundable|remaining|already_refunded|total_refunded|original|settled)", src, re.I):
        v.append("ADR-002.4: cumulative refund cap check missing")

    if not v:
        v.extend(_check_python_ast_safe_for_runtime(tree))
    if not v:
        fee_harness = '''
from decimal import Decimal
fn = next((obj for name, obj in list(globals().items()) if callable(obj) and "fee" in name.lower()), None)
if fn is not None:
    assert fn(1000, Decimal("25")) == 2
    assert fn(1000, Decimal("35")) == 4
'''
        v.extend(_run_isolated_runtime_check(src, fee_harness))

    return {
        "passed": len(v) == 0,
        "rule_violations": v,
        "details": {"verification_mode": "static_plus_isolated_subprocess"},
    }


def verify_double_entry_idempotency(code: str) -> dict[str, Any]:
    src = strip_markdown_fences(code)
    v: list[str] = []
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        return {"passed": False, "rule_violations": [f"SYNTAX: {exc}"], "details": {}}

    v.extend(_check_python_ast_no_float(tree))
    v.extend(_check_python_ast_no_print(tree))
    if "sha256" not in src.lower():
        v.append("ADR-002.3: missing SHA-256 request fingerprint")
    if "DEBIT" not in src or "CREDIT" not in src:
        v.append("ADR-002.2: DEBIT/CREDIT double-entry validation missing")
    if "idempotency_key" not in src:
        v.append("ADR-002.3: idempotency_key validation missing")
    if not re.search(r"(!=|==)", src):
        v.append("ADR-002.2/3: missing equality/conservation check")
    return {"passed": len(v) == 0, "rule_violations": v, "details": {}}


def verify_webhook_verifier(code: str) -> dict[str, Any]:
    src = strip_markdown_fences(code)
    v: list[str] = []
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        return {"passed": False, "rule_violations": [f"SYNTAX: {exc}"], "details": {}}

    v.extend(_check_python_ast_no_print(tree))
    if "compare_digest" not in src:
        v.append("ADR-003.1: must use hmac.compare_digest")
    if "json.dumps" in src:
        v.append("ADR-003.2: json.dumps prohibited on webhook payload verification; sign raw bytes")
    if "300" not in src or "abs(" not in src:
        v.append("ADR-003.3: must enforce symmetric abs(now - ts) <= 300 replay window")
    if "v1=" not in src:
        v.append("ADR-003.2: missing v1= signature prefix handling")
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            left_s = ast.unparse(node.left).lower()
            if any(tok in left_s for tok in ("sig", "digest", "hmac")) and any(isinstance(op, (ast.Eq, ast.NotEq)) for op in node.ops):
                v.append("ADR-003.1: direct == / != comparison on signature forbidden")
                break
    return {"passed": len(v) == 0, "rule_violations": v, "details": {}}


def verify_pii_redactor(code: str) -> dict[str, Any]:
    src = strip_markdown_fences(code)
    v: list[str] = []
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        return {"passed": False, "rule_violations": [f"SYNTAX: {exc}"], "details": {}}

    v.extend(_check_python_ast_no_print(tree))
    if "***REDACTED***" not in src:
        v.append("ADR-004.1: expected exact `***REDACTED***` replacement token")
    if "****" not in src:
        v.append("ADR-004.1: expected `****` last-4 masking for account/iban")
    for req_field in ("trace_id", "status", "title", "detail"):
        if req_field not in src:
            v.append(f"ADR-004.3: RFC 9457 error builder missing `{req_field}`")

    if not v:
        v.extend(_check_python_ast_safe_for_runtime(tree))
    if not v:
        pii_harness = '''
redact_fn = next((obj for name, obj in list(globals().items()) if callable(obj) and "redact" in name.lower()), None)
assert redact_fn is not None, "no redact* callable found"
out = redact_fn({"email": "x@y.com", "nested": [{"token": "tok_123", "iban": "DE8912345678"}]})
assert out["email"] == "***REDACTED***"
assert out["nested"][0]["token"] == "***REDACTED***"
assert out["nested"][0]["iban"].endswith("5678") and "DE89" not in out["nested"][0]["iban"]
'''
        v.extend(_run_isolated_runtime_check(src, pii_harness))

    return {
        "passed": len(v) == 0,
        "rule_violations": v,
        "details": {"verification_mode": "static_plus_isolated_subprocess"},
    }


def verify_retry_circuit_breaker(code: str) -> dict[str, Any]:
    src = strip_markdown_fences(code)
    v: list[str] = []
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        return {"passed": False, "rule_violations": [f"SYNTAX: {exc}"], "details": {}}

    v.extend(_check_python_ast_no_print(tree))
    for node in ast.walk(tree):
        if isinstance(node, ast.While) and isinstance(node.test, ast.Constant) and node.test.value is True:
            v.append("ADR-005.1: unbounded `while True:` retry loop prohibited")
            break
    if "random" not in src:
        v.append("ADR-005.1: missing jitter (`random.uniform`) in backoff")
    for code_num in ("408", "429", "502", "503", "504"):
        if code_num not in src:
            v.append(f"ADR-005.2: missing retryable status {code_num}")
            break
    if not re.search(r"(400|401|403|404|422)", src):
        v.append("ADR-005.2: missing non-retryable 4xx exclusion")
    if "OPEN" not in src or not re.search(r"(2\.0|connect)", src):
        v.append("ADR-005.3: missing explicit timeouts or CircuitBreaker OPEN check")
    return {"passed": len(v) == 0, "rule_violations": v, "details": {}}


def verify_tenant_sql_repo(code: str) -> dict[str, Any]:
    src = strip_markdown_fences(code)
    v: list[str] = []
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        return {"passed": False, "rule_violations": [f"SYNTAX: {exc}"], "details": {}}

    v.extend(_check_python_ast_no_print(tree))
    v.extend(_check_sql_string_interpolation(tree))
    if "tenant_id = %s" not in src and "tenant_id=%s" not in src:
        v.append("ADR-006.3: SQL WHERE predicate must bind `tenant_id = %s`")
    if not re.search(r"auth_ctx|AuthContext", src):
        v.append("ADR-006.1: repository must require AuthContext")
    if not re.search(r"!=|mismatch", src, re.I):
        v.append("ADR-006.1: missing tenant mismatch verification")
    return {"passed": len(v) == 0, "rule_violations": v, "details": {}}


def verify_rbac_guard(code: str) -> dict[str, Any]:
    src = strip_markdown_fences(code)
    v: list[str] = []
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        return {"passed": False, "rule_violations": [f"SYNTAX: {exc}"], "details": {}}

    v.extend(_check_python_ast_no_print(tree))
    for sc in ("ledger:read", "ledger:write", "webhook:admin", "migration:approve"):
        if sc not in src:
            v.append(f"ADR-006.2: missing allowed scope `{sc}`")
    if re.search(r'in\s+.*scopes.*or\s+["\']\*["\']', src) or re.search(r'["\']\*["\']\s+in\s+.*scopes', src):
        v.append("ADR-006.2: wildcard `*` scope bypass forbidden")
    if "admin" in src.lower() and "webhook:admin" not in src.lower():
        v.append("ADR-006.2: implicit role fallback (`admin`) prohibited")
    return {"passed": len(v) == 0, "rule_violations": v, "details": {}}


def verify_composite_refund_handler(code: str) -> dict[str, Any]:
    src = strip_markdown_fences(code)
    v: list[str] = []
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        return {"passed": False, "rule_violations": [f"SYNTAX: {exc}"], "details": {}}

    v.extend(_check_python_ast_no_float(tree))
    v.extend(_check_python_ast_no_print(tree))
    v.extend(_check_sql_string_interpolation(tree))
    if "Decimal" not in src or "ROUND_HALF_EVEN" not in src:
        v.append("ADR-002.1: refund fee math must use Decimal + ROUND_HALF_EVEN")
    if "idempotency_key" not in src:
        v.append("ADR-002.3: refund endpoint must enforce idempotency_key")
    if "ledger:write" not in src:
        v.append("ADR-006.2: refund handler must require `ledger:write` scope")
    if "redact" not in src.lower() and "***REDACTED***" not in src:
        v.append("ADR-004.1: refund handler logs must redact PII/secrets")
    if "tenant_id" not in src:
        v.append("ADR-006.1: refund handler must enforce tenant isolation")
    return {"passed": len(v) == 0, "rule_violations": v, "details": {}}


VERIFIER_REGISTRY = {
    "sql_index": verify_sql_index_migration,
    "sql_constraint": verify_sql_constraint_migration,
    "fee_refund": verify_fee_and_refund_module,
    "double_entry": verify_double_entry_idempotency,
    "webhook": verify_webhook_verifier,
    "pii_redactor": verify_pii_redactor,
    "retry_breaker": verify_retry_circuit_breaker,
    "tenant_sql": verify_tenant_sql_repo,
    "rbac_guard": verify_rbac_guard,
    "composite_refund": verify_composite_refund_handler,
}


def verify_task_output(verifier_kind: str, output_text: str) -> dict[str, Any]:
    fn = VERIFIER_REGISTRY.get(verifier_kind)
    if fn is None:
        raise ValueError(f"Unknown verifier kind: {verifier_kind}")
    return fn(output_text)


def audit_pr_drift(diff_text: str) -> list[dict[str, str]]:
    """Deterministic drift detector across raw unified git diff additions (`+` lines)."""
    added = "\n".join(ln[1:] for ln in diff_text.splitlines() if ln.startswith("+") and not ln.startswith("+++"))
    low = added.lower()
    findings: list[dict[str, str]] = []

    if "create index" in low and "concurrently" not in low:
        findings.append({"adr": "ADR-001.1", "severity": "HIGH", "finding": "Non-concurrent CREATE INDEX blocks table writes."})
    if ("create index" in low or "alter table" in low) and "lock_timeout" not in low:
        findings.append({"adr": "ADR-001.2", "severity": "HIGH", "finding": "SQL DDL lacks SET lock_timeout = '2s'."})
    if re.search(r"\bfloat\b|0\.\d+|round\(", added):
        findings.append({"adr": "ADR-002.1", "severity": "CRITICAL", "finding": "Binary float arithmetic or round() used in financial calculation."})
    if "json.dumps" in added and "hmac" in low:
        findings.append({"adr": "ADR-003.2", "severity": "HIGH", "finding": "HMAC computed over json.dumps instead of raw request bytes."})
    if re.search(r"signature\s*==|expected.*==.*provided|==\s*sig", low):
        findings.append({"adr": "ADR-003.1", "severity": "HIGH", "finding": "Direct == equality used on HMAC signature instead of hmac.compare_digest."})
    if re.search(r"\bprint\s*\(", added):
        findings.append({"adr": "ADR-004.2", "severity": "MEDIUM", "finding": "Bare print() statement in runtime code risks leaking unredacted PII."})
    if re.search(r'f["\'].*SELECT.*FROM|SELECT .* WHERE .* \+', added, flags=re.I):
        findings.append({"adr": "ADR-006.3", "severity": "CRITICAL", "finding": "Dynamic SQL string construction detected; use %s parameters with tenant_id = %s."})
    if '"*"' in added or "'*'" in added and "scope" in low:
        findings.append({"adr": "ADR-006.2", "severity": "HIGH", "finding": "Wildcard scope authorization forbidden."})
    return findings
