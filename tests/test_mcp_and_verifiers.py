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


def test_verifiers_use_isolated_subprocess_and_reject_unsafe_code(tmp_path) -> None:
    import inspect
    from meko_adlc import verifiers as vf

    src_text = inspect.getsource(vf)
    assert "compile(tree" not in src_text

    marker = tmp_path / "pwned.txt"
    evil_fee = f"""
from decimal import Decimal, ROUND_HALF_EVEN
import os
def compute_fee_minor(amount_minor: int, rate_bps: Decimal) -> int:
    os.write(1, b"nope")
    open({str(marker)!r}, "w").write("pwned")
    return int(((Decimal(amount_minor) * Decimal(str(rate_bps))) / Decimal("10000")).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN))
def validate_refund_request(tenant_id: str, idempotency_key: str, settled_minor: int, already_refunded_minor: int, refund_minor: int) -> int:
    return settled_minor - already_refunded_minor - refund_minor
"""
    evil_res = verify_task_output("fee_refund", evil_fee)
    assert not evil_res["passed"]
    assert any("SECURITY:" in item for item in evil_res["rule_violations"])
    assert not marker.exists()

    good_fee = """
from decimal import Decimal, ROUND_HALF_EVEN
def compute_fee_minor(amount_minor: int, rate_bps: Decimal | str | int) -> int:
    return int(((Decimal(amount_minor) * Decimal(str(rate_bps))) / Decimal("10000")).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN))
def validate_refund_request(tenant_id: str, idempotency_key: str, settled_minor: int, already_refunded_minor: int, refund_minor: int) -> int:
    if already_refunded_minor + refund_minor > settled_minor:
        raise ValueError("cap")
    return settled_minor - already_refunded_minor - refund_minor
"""
    good_res = verify_task_output("fee_refund", good_fee)
    assert good_res["passed"]
    assert good_res["details"]["verification_mode"] == "static_plus_isolated_subprocess"


def test_benchmark_retry_tracks_monotonic_total_and_attempt_timings(monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess
    import time
    from meko_adlc import benchmark as bm

    calls = {"n": 0}

    def fake_run(cmd, prompt, *, unset_env=(), timeout_s=120.0, cwd="/tmp"):
        calls["n"] += 1
        if calls["n"] == 1:
            time.sleep(0.03)
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=0.05)
        return "ok", 0.04

    monkeypatch.setattr(bm, "run_cli_prompt", fake_run)
    out, last_s, total_s, retries, timings = bm._run_cli_with_retry(["commandcode"], "prompt", timeout_s=0.05, max_retries=1)
    assert out == "ok"
    assert last_s == pytest.approx(0.04)
    assert total_s >= 0.025
    assert retries == 1
    assert len(timings) == 2
    assert timings[0]["status"] == "timeout"
    assert timings[1]["status"] == "ok"


def test_sanitize_public_report_strips_s3_auth_preserving_code() -> None:
    from meko_adlc.workflows import sanitize_public_report

    dirty = {
        "kb_fix": {
            "init": {
                "datapack_id": "dp-1",
                "url": "https://bucket.s3.amazonaws.com",
                "fields": {
                    "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
                    "X-Amz-Credential": "AKIA1234567890ABCDEF/20261122/us-east-2/s3/aws4_request",
                    "X-Amz-Signature": "deadbeef1234",
                    "policy": "eyJjb25kaXRpb25zIjpbXX0=",
                    "key": "safe-doc-key.txt",
                },
            },
            "status": {"state": "completed"},
        },
        "note": "API token mko_live_secret_value_abc123 must stay hidden",
        "code": "def verify_webhook(signature_header: str): return signature_header",
    }
    clean = sanitize_public_report(dirty)
    dumped = json.dumps(clean)
    assert "X-Amz-" not in dumped
    assert "AKIA1234567890ABCDEF" not in dumped
    assert "deadbeef1234" not in dumped
    assert "mko_live_secret_value_abc123" not in dumped
    assert "bucket.s3.amazonaws.com" not in dumped
    assert clean["kb_fix"]["status"]["state"] == "completed"
    assert "signature_header" in clean["code"]


def test_handoff_agent23_dynamic_provenance_and_sha256(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    import base64
    import hashlib
    from meko_adlc import workflows as wf

    sql_bytes = (
        b"SET lock_timeout = '2s';\n"
        b"SET statement_timeout = '30s';\n"
        b"CREATE TABLE IF NOT EXISTS ledger_refunds (refund_id BIGINT PRIMARY KEY, tenant_id TEXT NOT NULL, idempotency_key VARCHAR(128) NOT NULL, UNIQUE (tenant_id, idempotency_key));\n"
        b"ALTER TABLE ledger_refunds ADD CONSTRAINT chk_pos CHECK (refund_id > 0) NOT VALID;\n"
        b"ALTER TABLE ledger_refunds VALIDATE CONSTRAINT chk_pos;\n"
    )
    good_hash = hashlib.sha256(sql_bytes).hexdigest()

    class FakeClient:
        def __init__(self, fail_cross_agent: bool = False) -> None:
            self.fail_cross_agent = fail_cross_agent
            self.seq = 0

        def conversation_create(self, **kwargs):
            self.seq += 1
            return {"conversation_id": f"cid-{self.seq}"}

        def conversation_get(self, conversation_id, **kwargs):
            return {"conversation_id": conversation_id, "messages": []}

        def context_search(self, **kwargs):
            return {"results": {"knowledge_base": []}}

        def memory_search(self, **kwargs):
            return {"results": []}

        def artifact_get(self, artifact_hash, *, conversation_id, agent_id=None):
            if self.fail_cross_agent and agent_id == "codex-verifier":
                raise MekoToolError("cross-agent denied")
            return {"content_base64": base64.b64encode(sql_bytes).decode("ascii")}

        def artifact_put(self, *args, **kwargs):
            return {"hash": "rev-art-1"}

        def conversation_add_message(self, **kwargs):
            return {"ok": True}

        def track_token_usage(self, *args, **kwargs):
            return {"ok": True}

    monkeypatch.setattr(wf, "run_cli_prompt", lambda *a, **kw: ("def verify_migration_sql(s): return []", 0.2))

    # Case 1: Linked Agent 1 report carries exact observed values & SHA-256 passes
    a1_file = tmp_path / "a1.json"
    a1_file.write_text(
        json.dumps({
            "conversation_id": "conv-a1-real",
            "agent_id": "claude-code-architect",
            "memory_ids": ["mem-custom-999"],
            "artifact_hash": good_hash,
            "verifier": {"passed": False, "rule_violations": ["ADR-001.2: sample"]},
            "tokens": {"input": 420, "output": 111},
        }),
        encoding="utf-8",
    )
    res1 = wf.run_handoff_agent23_mbp(FakeClient(fail_cross_agent=True), tmp_path, "conv-a1-real", good_hash, agent1_report_path=a1_file)
    assert res1["agent1_claude"]["provenance"] == "linked_agent1_report"
    assert res1["agent1_claude"]["memory_ids"] == ["mem-custom-999"]
    assert res1["agent1_claude"]["verifier"]["passed"] is False
    assert res1["agent1_claude"]["tokens"] == {"input": 420, "output": 111}
    assert res1["agent2_codex"]["artifact_access_mode"] == "creator_scoped"
    assert res1["agent2_codex"]["artifact_sha256_verified"] is True

    # Case 2: No Agent 1 report & wrong hash -> honest external_unverified & sha256 mismatch
    res2 = wf.run_handoff_agent23_mbp(FakeClient(fail_cross_agent=False), tmp_path, "conv-ext", "0" * 64)
    assert res2["agent1_claude"]["provenance"] == "external_unverified"
    assert res2["agent1_claude"]["memory_ids"] == []
    assert res2["agent1_claude"]["verifier"] is None
    assert "3ab4a2a2" not in json.dumps(res2)
    assert res2["agent2_codex"]["artifact_access_mode"] == "cross_agent"
    assert res2["agent2_codex"]["artifact_sha256_verified"] is False


def test_amp_refuses_delete_without_opt_in_and_tracks_cleanup(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    from meko_adlc import workflows as wf

    deleted_calls: list[str] = []

    class FakeAmpClient:
        def conversation_create(self, **kwargs):
            return {"conversation_id": "conv-amp"}

        def amp_core_budget(self, *, conversation_id):
            return {"used_vcpu": 0.0, "max_vcpu": 0.5}

        def amp_cluster_list(self, cid):
            return {"clusters": [{"id": "cl-existing", "name": "adlc-ledger-db"}]}

        def amp_cluster_delete(self, cluster_id, cid):
            deleted_calls.append(cluster_id)
            return {"deleted": True}

        def conversation_add_message(self, **kwargs):
            return {"ok": True}

    monkeypatch.setattr(wf, "_get_public_ipv4", lambda: "203.0.113.10")
    monkeypatch.delenv("MEKO_AMP_ADMIN_PW", raising=False)

    out = wf.run_amp_branch_check(FakeAmpClient(), tmp_path, recreate_if_missing_pw=False)
    assert deleted_calls == []
    assert out["verified"] is False
    assert "recreate-if-missing-pw" in out["error"]


def test_cli_doctor_and_replay_audit_offline(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    from meko_adlc import cli

    data_dir = tmp_path / "data"
    portal_data = tmp_path / "portal" / "src" / "data"
    data_dir.mkdir(parents=True)
    portal_data.mkdir(parents=True)

    sample_files = {
        "seed_report.json": {"conversation_id": "c1", "datapack": {"knowledge_chunk_count": 10}},
        "amp_report.json": {"cluster_id": "cl1", "fork_branch": {"name": "b1"}, "main_wal_lsn": "0/1", "cow_inherited_account_rows": 1, "negative_amount_check_violation_enforced": True, "status": "amp_branch_verified"},
        "handoff_report.json": {"run_id": "r1", "agent1_claude": {"agent_id": "a1", "provenance": "linked_agent1_report", "memory_ids": [], "artifact_hash": "h"}, "agent2_codex": {"agent_id": "a2", "conversation_id": "c2", "artifact_access_mode": "cross_agent", "sql_check": {"passed": True}}, "agent3_review": {"agent_id": "a3", "conversation_id": "c3", "findings": []}},
        "selflearning_report.json": {"selflearning_verify": {"before_best_score": 0.3, "before_band": "low", "after_best_score": 0.86, "after_band": "high", "hits_above_mid": 2}},
        "benchmark_results.json": {"summary": {"baseline": {"passed_count": 9, "total_violations": 2, "prompt_tokens": 100, "total_tokens": 120, "reference_cost_usd": 0.1, "avg_latency_s": 10.0}, "meko": {"passed_count": 10, "total_violations": 0, "prompt_tokens": 10, "total_tokens": 20, "reference_cost_usd": 0.02, "avg_latency_s": 20.0}, "deltas": {"prompt_token_reduction_pct": 90.0, "total_token_reduction_pct": 83.3, "cost_reduction_pct": 80.0, "latency_change_pct": 100.0}, "retry_inclusive_lower_bound_avg_s": 25.0, "retry_inclusive_lower_bound_change_pct": 150.0}},
        "exported_traces.json": {"datapack_name": "contextcon-adlc", "datapack_id": "dp-1", "exported_at": "2026-11-22T09:00:00Z", "traces_attempted": 1, "traces_fetched_ok": 1, "fetch_errors_count": 0, "conversations": [{"id": "c1"}], "memories": {"memories": []}, "selflearning_status": {"searches": {"total": 1, "zero_results": 0, "avg_score": 0.8}}},
    }
    for name, obj in sample_files.items():
        (data_dir / name).write_text(json.dumps(obj, indent=2), encoding="utf-8")

    monkeypatch.delenv("MEKO_API_KEY", raising=False)
    monkeypatch.delenv("MEKO_DATAPACK_ID", raising=False)

    cli.export_portal_data(None, tmp_path, rebuild_snapshot_only=True)
    snap_bytes = (data_dir / "portal_snapshot.json").read_bytes()
    (portal_data / "portal_snapshot.json").write_bytes(snap_bytes)

    doc_clean, rc_clean = cli.run_doctor(tmp_path)
    assert rc_clean == 0 and doc_clean["ok"] is True

    replay = cli.run_replay_audit(tmp_path)
    assert "OFFLINE AUDIT REPLAY OF CAPTURED RUNS" in replay
    assert "0.3 (low) -> 0.86 (high)" in replay

    # Leak check catches AKIA key
    (data_dir / "selflearning_report.json").write_text(json.dumps({"leak": "AKIA1234567890ABCDEF"}), encoding="utf-8")
    doc_dirty, rc_dirty = cli.run_doctor(tmp_path)
    assert rc_dirty == 1 and doc_dirty["ok"] is False and doc_dirty["secret_leaks"]
