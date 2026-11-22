"""Unit tests for pure-stdlib Meko MCP parser, config redaction, and deterministic verifiers."""

import json
import pytest

from meko_adlc.config import MekoConfig
from meko_adlc.mcp_client import MekoMCPClient, MekoToolError, parse_mcp_http_payload, unwrap_tool_result
from meko_adlc.verifiers import audit_pr_drift, verify_task_output


def test_config_repr_masks_secret() -> None:
    cfg = MekoConfig("mko_super_secret_token_value_12345", "https://mcp.mekodata.ai/mcp", "dp-1", "contextcon-adlc")
    rep = repr(cfg)
    assert "super_secret" not in rep
    assert "mko_***" in rep


def test_sse_parse_and_error_unwrapping() -> None:
    inner = json.dumps({"ok": True, "count": 5})
    envelope = json.dumps({"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": inner}], "isError": False}})
    sse = f"event: message\ndata: {envelope}\n\n".encode("utf-8")
    parsed = parse_mcp_http_payload(sse, "text/event-stream")
    unwrapped = unwrap_tool_result(parsed)
    assert unwrapped == {"ok": True, "count": 5}

    err_rpc = {
        "jsonrpc": "2.0",
        "id": 2,
        "result": {
            "content": [{"type": "text", "text": '{"error": "conversation_id_required"}'}],
            "isError": False,
        },
    }
    with pytest.raises(MekoToolError, match="conversation_id_required"):
        unwrap_tool_result(err_rpc)


def test_encode_multipart_form_data_orders_fields_before_file() -> None:
    from meko_adlc.mcp_client import encode_multipart_form_data
    body, ctype = encode_multipart_form_data({"key": "k1", "policy": "p1"}, "file", "a.md", b"hello", boundary="B123")
    assert ctype == "multipart/form-data; boundary=B123"
    pos_key = body.find(b'name="key"')
    pos_pol = body.find(b'name="policy"')
    pos_file = body.find(b'name="file"; filename="a.md"')
    assert 0 <= pos_key < pos_pol < pos_file
    assert b"hello\r\n--B123--" in body


def test_conversation_get_forwards_agent_id() -> None:
    cfg = MekoConfig("mko_dummy_token_1234567890", "https://mcp.mekodata.ai/mcp", "dp-1", "contextcon-adlc")
    c = MekoMCPClient(cfg)
    captured = {}
    def fake_call(name, arguments=None, *, require_conv=True):
        captured["name"] = name
        captured["arguments"] = arguments
        return {"ok": True}
    c.call_tool = fake_call  # type: ignore[method-assign]
    c.conversation_get("conv-1", include_messages=True, limit=10, agent_id="claude-code-architect")
    assert captured["name"] == "conversation_get"
    assert captured["arguments"]["agent_id"] == "claude-code-architect"


def test_sql_verifier_catches_bad_vs_good() -> None:
    bad = "CREATE INDEX idx_x ON journal_lines (reference_id);"
    r_bad = verify_task_output("sql_index", bad)
    assert not r_bad["passed"] and len(r_bad["rule_violations"]) >= 3

    good = (
        "-- migrate:no-transaction\n"
        "SET lock_timeout = '2s';\n"
        "SET statement_timeout = '30s';\n"
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_x ON journal_lines (tenant_id, reference_id);"
    )
    r_good = verify_task_output("sql_index", good)
    assert r_good["passed"] and r_good["rule_violations"] == []


def test_fee_and_pii_verifiers() -> None:
    bad_fee = "def compute_fee(a, b): return round(a * 0.025, 2)"
    assert not verify_task_output("fee_refund", bad_fee)["passed"]

    bad_pii = "def redact(d):\n    print(d)\n    return d"
    assert not verify_task_output("pii_redactor", bad_pii)["passed"]

    good_pii = """
from typing import Any
def redact_payload(d: Any) -> Any:
    if isinstance(d, dict):
        out = {}
        for k, v in d.items():
            kl = k.lower()
            if "iban" in kl:
                out[k] = "****" + str(v)[-4:]
            elif any(x in kl for x in ("email", "token", "secret", "password", "api_key")):
                out[k] = "***REDACTED***"
            else:
                out[k] = redact_payload(v)
        return out
    if isinstance(d, list):
        return [redact_payload(x) for x in d]
    return d
def build_error(status: int, title: str, detail: str, trace_id: str) -> dict[str, Any]:
    return {"type": "about:blank", "status": status, "title": title, "detail": detail, "trace_id": trace_id}
"""
    assert verify_task_output("pii_redactor", good_pii)["passed"]


def test_audit_pr_drift_detects_violations() -> None:
    diff = """
+++ b/ledger_service/bad_pr.py
+CREATE INDEX idx_bad ON journal_lines (entry_id);
+fee = round(amount * 0.029, 2)
+if computed_sig == sig:
+    print("ok", api_key)
+sql = f"SELECT * FROM accounts WHERE id = '{acct_id}'"
"""
    findings = audit_pr_drift(diff)
    adrs = {f["adr"] for f in findings}
    assert {"ADR-001.1", "ADR-001.2", "ADR-002.1", "ADR-003.1", "ADR-004.2", "ADR-006.3"} <= adrs


def test_verifier_allows_defensive_isinstance_float_guard() -> None:
    guard_ok = """
from decimal import Decimal, ROUND_HALF_EVEN
def compute_fee_minor(amount_minor: int, rate_bps: Decimal | int | str) -> int:
    if isinstance(rate_bps, float):
        raise ValueError("float prohibited")
    return int(((Decimal(amount_minor) * Decimal(str(rate_bps))) / Decimal("10000")).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN))
def validate_refund_request(tenant_id: str, idempotency_key: str, settled_minor: int, already_refunded_minor: int, refund_minor: int) -> int:
    if not idempotency_key.strip() or already_refunded_minor + refund_minor > settled_minor:
        raise ValueError("exceeds refundable balance")
    return settled_minor - already_refunded_minor - refund_minor
"""
    res = verify_task_output("fee_refund", guard_ok)
    assert res["passed"] and res["rule_violations"] == []

    bad_type = """
from decimal import Decimal, ROUND_HALF_EVEN
def compute_fee_minor(amount_minor: int, rate_bps: float) -> int:
    return int(((Decimal(amount_minor) * Decimal(str(rate_bps))) / Decimal("10000")).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN))
def validate_refund_request(tenant_id: str, idempotency_key: str, settled_minor: int, already_refunded_minor: int, refund_minor: int) -> int:
    return settled_minor - already_refunded_minor - refund_minor
"""
    res_bad = verify_task_output("fee_refund", bad_type)
    assert not res_bad["passed"] and any("float" in v for v in res_bad["rule_violations"])
def test_format_meko_context_respects_max_kb_and_mem() -> None:
    from meko_adlc.benchmark import _format_meko_context

    payload = {
        "results": {
            "knowledge_base": [
                {"chunk_text": f"kb chunk {i}", "rerank_score": round(0.9 - i * 0.05, 2)}
                for i in range(1, 9)
            ],
            "memory": [
                {"memory": f"mem item {i}", "score": round(0.8 - i * 0.1, 2)}
                for i in range(1, 6)
            ],
        }
    }
    formatted = _format_meko_context(payload, max_kb=6, max_mem=3)
    assert "[KB #6 score=" in formatted
    assert "[KB #7" not in formatted
    assert "[Memory #3 score=" in formatted
    assert "[Memory #4" not in formatted


def test_benchmark_checkpoint_and_resume_merges_batches(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    import shutil
    from pathlib import Path
    from meko_adlc import benchmark as bm

    repo_root = Path(__file__).resolve().parents[1]
    shutil.copytree(repo_root / "docs", tmp_path / "docs")
    shutil.copytree(repo_root / "target_repo", tmp_path / "target_repo")

    calls: list[str] = []

    class FakeClient:
        def __init__(self) -> None:
            self.conv_creates = 0
            self.search_limits: list[int] = []

        def conversation_create(self, **kwargs):
            self.conv_creates += 1
            return {"conversation_id": "conv-bench-resume"}

        def context_search(self, **kwargs):
            self.search_limits.append(int(kwargs["limit"]))
            return {"results": {"knowledge_base": [{"chunk_text": "-- migrate:no-transaction\nSET lock_timeout = '2s';\nSET statement_timeout = '30s';\nCREATE INDEX CONCURRENTLY idx ON t(a);", "rerank_score": 0.9}], "memory": []}}

        def conversation_add_message(self, **kwargs):
            return {"ok": True}

        def track_token_usage(self, *args, **kwargs):
            return {"ok": True}

    def fake_run_cli_prompt(cmd, prompt, *, unset_env=(), timeout_s=120.0, cwd="/tmp"):
        if "TASK T01" in prompt:
            calls.append("T01")
            return (
                "```sql\n-- migrate:no-transaction\nSET lock_timeout = '2s';\nSET statement_timeout = '30s';\nCREATE INDEX CONCURRENTLY idx_journal_lines_ref ON journal_lines (tenant_id, reference_id);\n```",
                0.1,
            )
        if "TASK T02" in prompt:
            calls.append("T02")
            return (
                "```python\nfrom decimal import Decimal, ROUND_HALF_EVEN\ndef compute_fee_minor(amount_minor: int, rate_bps):\n    return int(((Decimal(amount_minor) * Decimal(str(rate_bps))) / Decimal('10000')).quantize(Decimal('1'), rounding=ROUND_HALF_EVEN))\ndef validate_refund_request(tenant_id, idempotency_key, settled_minor, already_refunded_minor, refund_minor):\n    return settled_minor - already_refunded_minor - refund_minor\n```",
                0.2,
            )
        raise AssertionError(f"Unexpected task prompt: {prompt[:120]}")

    monkeypatch.setattr(bm, "run_cli_prompt", fake_run_cli_prompt)
    client = FakeClient()

    b1 = bm.run_paired_benchmark(client, tmp_path, resume=False, task_ids=["T01"], search_limit=6, timeout_s=240.0)
    assert b1["partial_tasks"] == 1
    assert b1["conversation_id"] == "conv-bench-resume"
    assert calls == ["T01", "T01"]

    b2 = bm.run_paired_benchmark(client, tmp_path, resume=True, task_ids=["T01", "T02"], search_limit=6, timeout_s=240.0)
    assert b2["partial_tasks"] == 2
    assert [t["task_id"] for t in b2["tasks"]] == ["T01", "T02"]
    assert client.conv_creates == 1
    assert client.search_limits == [6, 6]
    assert calls == ["T01", "T01", "T02", "T02"]
