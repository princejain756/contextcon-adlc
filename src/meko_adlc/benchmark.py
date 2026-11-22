"""Paired 10-task Baseline vs Meko Shared Context benchmark on DeepSeek V4.1 Flash."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from meko_adlc.mcp_client import MekoMCPClient
from meko_adlc.verifiers import verify_task_output
from meko_adlc.workflows import count_tokens, run_cli_prompt

INPUT_USD_PER_M = 3.0
OUTPUT_USD_PER_M = 15.0


@dataclass(frozen=True)
class BenchmarkTask:
    task_id: str
    title: str
    verifier_kind: str
    search_query: str
    prompt: str
    output_lang: str


TASKS: tuple[BenchmarkTask, ...] = (
    BenchmarkTask(
        "T01",
        "Zero-Downtime Lookup Index Migration",
        "sql_index",
        "ADR-001 CREATE INDEX CONCURRENTLY NO_TX migrate:no-transaction lock_timeout statement_timeout",
        "Write PostgreSQL migration SQL to add a composite lookup index named `idx_journal_lines_ref` on `journal_lines (tenant_id, reference_id)` following all team migration standards. Return ONLY SQL inside ```sql fences.",
        "sql",
    ),
    BenchmarkTask(
        "T02",
        "Fee Calculator & Cumulative Refund Cap",
        "fee_refund",
        "ADR-002 fee calculation Decimal ROUND_HALF_EVEN zero float refund cap idempotency_key",
        "Write a self-contained Python module defining `compute_fee_minor(amount_minor: int, rate_bps)` and `validate_refund_request(tenant_id: str, idempotency_key: str, settled_minor: int, already_refunded_minor: int, refund_minor: int)` conforming to all ledger precision and refund standards. Return ONLY Python inside ```python fences.",
        "python",
    ),
    BenchmarkTask(
        "T03",
        "Double-Entry Transfer & Request Fingerprint",
        "double_entry",
        "ADR-002 double-entry DEBIT CREDIT sum conservation SHA-256 request_hash idempotency_key",
        "Write a self-contained Python module defining `PostingLine`, `compute_request_hash(...)`, and `post_transfer(store, tenant_id, idempotency_key, currency, lines)` validating double-entry DEBIT/CREDIT balance and idempotency conflicts. Return ONLY Python inside ```python fences.",
        "python",
    ),
    BenchmarkTask(
        "T04",
        "Webhook HMAC Signature & Replay Window",
        "webhook",
        "ADR-003 webhook hmac.compare_digest raw_body v1= replay drift 300 seconds",
        "Write a self-contained Python function `verify_webhook(secret: str, timestamp_header: str, signature_header: str, raw_body: bytes, now_epoch: int | None = None) -> bool` conforming strictly to team webhook standards. Return ONLY Python inside ```python fences.",
        "python",
    ),
    BenchmarkTask(
        "T05",
        "Nested PII Redaction & RFC 9457 Error Builder",
        "pii_redactor",
        "ADR-004 redact_payload ***REDACTED*** mask_last4 **** trace_id RFC 9457 status title detail",
        "Write a self-contained Python module implementing `redact_payload(value)` and `build_error_response(status: int, title: str, detail: str, trace_id: str, extras: dict | None = None)` conforming strictly to team PII redaction and error standards (no bare print calls). Return ONLY Python inside ```python fences.",
        "python",
    ),
    BenchmarkTask(
        "T06",
        "Bounded Jittered Retry Client & Circuit Breaker",
        "retry_breaker",
        "ADR-005 retry max_attempts <= 4 jitter random 408 429 502 503 504 CircuitBreaker OPEN timeouts",
        "Write a self-contained Python module implementing `CircuitBreaker` and `execute_retry(call_fn, breaker, max_attempts=3)` conforming strictly to team retry, backoff jitter, status code allowlist, timeout tuple, and breaker standards. Return ONLY Python inside ```python fences.",
        "python",
    ),
    BenchmarkTask(
        "T07",
        "Tenant-Isolated Parameterized SQL Queries",
        "tenant_sql",
        "ADR-006 AuthContext tenant_id mismatch WHERE tenant_id = %s parameterized SQL",
        "Write a self-contained Python module implementing `AuthContext`, `enforce_tenant(auth_ctx, request_tenant_id)`, and `build_ledger_queries(auth_ctx, entry_id)` returning `(sql, params)` tuples conforming to all tenant isolation and SQL rules. Return ONLY Python inside ```python fences.",
        "python",
    ),
    BenchmarkTask(
        "T08",
        "Default-Deny Exact RBAC Scope Guard",
        "rbac_guard",
        "ADR-006 ALLOWED_SCOPES ledger:read ledger:write webhook:admin migration:approve no wildcard",
        "Write a self-contained Python module implementing `PermissionDeniedError`, `ALLOWED_SCOPES`, and `require_scope(auth_ctx, required_scope)` conforming strictly to team RBAC scope rules. Return ONLY Python inside ```python fences.",
        "python",
    ),
    BenchmarkTask(
        "T09",
        "Two-Phase CHECK Constraint Migration",
        "sql_constraint",
        "ADR-001 NOT VALID VALIDATE CONSTRAINT SET lock_timeout statement_timeout no SERIAL BIGSERIAL",
        "Write PostgreSQL migration SQL to add column `fee_minor BIGINT NOT NULL DEFAULT 0` and enforce positive check constraint `chk_fee_nonnegative CHECK (fee_minor >= 0)` on `journal_entries` safely following all zero-downtime migration standards. Return ONLY SQL inside ```sql fences.",
        "sql",
    ),
    BenchmarkTask(
        "T10",
        "Cross-ADR Tenant Refund Command Handler",
        "composite_refund",
        "ADR-002 Decimal ROUND_HALF_EVEN idempotency_key ADR-004 redact ***REDACTED*** ADR-006 ledger:write tenant_id",
        "Write a self-contained Python function `handle_refund_command(auth_ctx, idempotency_key: str, settled_minor: int, already_refunded_minor: int, refund_minor: int, fee_bps, audit_meta: dict)` enforcing RBAC `ledger:write`, tenant scoping, Decimal fee rounding, idempotency, and PII-safe structured log payload construction. Return ONLY Python inside ```python fences.",
        "python",
    ),
)


def load_full_repo_baseline_context(repo_dir: Path) -> str:
    chunks: list[str] = []
    for p in sorted((repo_dir / "docs" / "standards").glob("*.md")):
        chunks.append(f"### FILE: {p.name}\n" + p.read_text(encoding="utf-8"))
    for p in sorted((repo_dir / "target_repo" / "ledger_service").glob("*.py")):
        chunks.append(f"### FILE: target_repo/ledger_service/{p.name}\n" + p.read_text(encoding="utf-8"))
    for p in sorted((repo_dir / "target_repo" / "sql" / "migrations").glob("*.sql")):
        chunks.append(f"### FILE: target_repo/sql/migrations/{p.name}\n" + p.read_text(encoding="utf-8"))
    return "\n\n".join(chunks)


def _format_meko_context(search_res: Any, max_kb: int = 6, max_mem: int = 3) -> str:
    """Format compact retrieved KB + memory passages without noisy UUID/metadata JSON."""
    parts: list[str] = []
    results = search_res.get("results") if isinstance(search_res, dict) else {}
    if isinstance(results, dict):
        for idx, item in enumerate((results.get("knowledge_base") or [])[:max_kb], 1):
            if not isinstance(item, dict):
                continue
            txt = (item.get("chunk_text") or item.get("text") or "").strip()
            score = item.get("rerank_score") or item.get("rank") or item.get("distance") or ""
            if txt:
                parts.append(f"[KB #{idx} score={score}]\n{txt}")
        for idx, item in enumerate((results.get("memory") or [])[:max_mem], 1):
            if not isinstance(item, dict):
                continue
            txt = (item.get("memory") or item.get("text") or "").strip()
            score = item.get("score") or ""
            if txt:
                parts.append(f"[Memory #{idx} score={score}]\n{txt}")
    if not parts:
        return json.dumps(search_res, indent=2)[:8000]
    return "\n\n---\n\n".join(parts)[:14000]


def _ref_cost_usd(in_tok: int, out_tok: int) -> float:
    return round((in_tok * INPUT_USD_PER_M + out_tok * OUTPUT_USD_PER_M) / 1_000_000.0, 6)


def _run_cli_with_retry(
    cmd: list[str],
    prompt: str,
    *,
    timeout_s: float = 240.0,
    max_retries: int = 1,
    cwd: str = "/tmp",
) -> tuple[str, float, float, int, list[dict[str, Any]]]:
    """Run CLI prompt with monotonic retry-inclusive timing and per-attempt diagnostics."""
    t_total0 = time.perf_counter()
    attempt_timings: list[dict[str, Any]] = []
    for attempt in range(max_retries + 1):
        t_attempt0 = time.perf_counter()
        try:
            out, elapsed = run_cli_prompt(cmd, prompt, timeout_s=timeout_s, cwd=cwd)
            attempt_timings.append({"attempt": attempt + 1, "status": "ok", "elapsed_s": round(elapsed, 3)})
            total_elapsed = time.perf_counter() - t_total0
            return out, elapsed, total_elapsed, attempt, attempt_timings
        except subprocess.TimeoutExpired as exc:
            timed_out_s = getattr(exc, "timeout", None) or (time.perf_counter() - t_attempt0)
            attempt_timings.append(
                {
                    "attempt": attempt + 1,
                    "status": "timeout",
                    "elapsed_s": round(float(timed_out_s), 3),
                }
            )
            if attempt >= max_retries:
                raise
            print(
                f"[BENCH RETRY] CLI {cmd[0]} timed out after {timeout_s}s (attempt {attempt + 1}/{max_retries + 1}); retrying...",
                file=sys.stderr,
                flush=True,
            )
    raise AssertionError("unreachable")


def _build_benchmark_summary(
    ordered_results: list[dict[str, Any]],
    *,
    baseline_ctx_tokens: int,
    cid: str,
    search_limit: int,
) -> dict[str, Any]:
    n = len(ordered_results)
    b_tot_tok = sum(r["baseline"]["total_tokens"] for r in ordered_results)
    m_tot_tok = sum(r["meko"]["total_tokens"] for r in ordered_results)
    b_in_sum = sum(r["baseline"]["prompt_tokens"] for r in ordered_results)
    m_in_sum = sum(r["meko"]["prompt_tokens"] for r in ordered_results)
    b_pass = sum(1 for r in ordered_results if r["baseline"]["passed"])
    m_pass = sum(1 for r in ordered_results if r["meko"]["passed"])
    b_viol = sum(r["baseline"]["violation_count"] for r in ordered_results)
    m_viol = sum(r["meko"]["violation_count"] for r in ordered_results)
    b_lat = sum(r["baseline"]["latency_s"] for r in ordered_results)
    b_e2e_lat = sum(r["baseline"].get("end_to_end_latency_s", r["baseline"]["latency_s"]) for r in ordered_results)
    m_lat = sum(r["meko"]["total_latency_s"] for r in ordered_results)
    m_e2e_lat = sum(r["meko"].get("end_to_end_total_latency_s", r["meko"]["total_latency_s"]) for r in ordered_results)
    b_cost = round(sum(r["baseline"]["reference_cost_usd"] for r in ordered_results), 6)
    m_cost = round(sum(r["meko"]["reference_cost_usd"] for r in ordered_results), 6)

    return {
        "model": "deepseek/deepseek-v4.1-flash",
        "effort": "low",
        "cwd": "/tmp",
        "tokenizer": "cl100k_base",
        "reference_pricing": "USD 3.00 / 1M input tokens, USD 15.00 / 1M output tokens",
        "corpus": "symmetric_18_files",
        "search_limit": search_limit,
        "baseline_repo_context_tokens": baseline_ctx_tokens,
        "conversation_id": cid,
        "task_count": n,
        "baseline": {
            "total_tokens": b_tot_tok,
            "prompt_tokens": b_in_sum,
            "avg_tokens_per_task": round(b_tot_tok / max(1, n), 1),
            "avg_latency_s": round(b_lat / max(1, n), 3),
            "end_to_end_avg_latency_s": round(b_e2e_lat / max(1, n), 3),
            "reference_cost_usd": b_cost,
            "passed_count": b_pass,
            "total_violations": b_viol,
        },
        "meko": {
            "total_tokens": m_tot_tok,
            "prompt_tokens": m_in_sum,
            "avg_tokens_per_task": round(m_tot_tok / max(1, n), 1),
            "avg_latency_s": round(m_lat / max(1, n), 3),
            "end_to_end_avg_latency_s": round(m_e2e_lat / max(1, n), 3),
            "reference_cost_usd": m_cost,
            "passed_count": m_pass,
            "total_violations": m_viol,
        },
        "deltas": {
            "prompt_token_reduction_pct": round((1.0 - m_in_sum / max(1, b_in_sum)) * 100.0, 2),
            "total_token_reduction_pct": round((1.0 - m_tot_tok / max(1, b_tot_tok)) * 100.0, 2),
            "cost_reduction_pct": round((1.0 - m_cost / max(1e-9, b_cost)) * 100.0, 2),
            "latency_change_pct": round((m_lat - b_lat) / max(1e-9, b_lat) * 100.0, 2),
            "end_to_end_latency_change_pct": round((m_e2e_lat - b_e2e_lat) / max(1e-9, b_e2e_lat) * 100.0, 2),
        },
    }


def run_paired_benchmark(
    client: MekoMCPClient,
    repo_dir: Path,
    *,
    resume: bool = False,
    task_ids: list[str] | None = None,
    search_limit: int = 6,
    timeout_s: float = 240.0,
) -> dict[str, Any]:
    data_dir = repo_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    out_path = data_dir / "benchmark_results.json"

    valid_ids = {t.task_id for t in TASKS}
    wanted_ids: set[str] | None = None
    if task_ids is not None:
        cleaned = [tid.strip().upper() for tid in task_ids if tid.strip()]
        if cleaned:
            unknown = [tid for tid in cleaned if tid not in valid_ids]
            if unknown:
                raise ValueError(f"Unknown task_id(s): {unknown}")
            wanted_ids = set(cleaned)

    baseline_ctx = load_full_repo_baseline_context(repo_dir)
    baseline_ctx_tokens = count_tokens(baseline_ctx)

    completed_by_id: dict[str, dict[str, Any]] = {}
    cid: str | None = None
    if resume and out_path.is_file():
        prev = json.loads(out_path.read_text(encoding="utf-8"))
        for row in prev.get("tasks") or []:
            if isinstance(row, dict) and row.get("task_id") in valid_ids:
                completed_by_id[str(row["task_id"])] = row
        cid_raw = prev.get("conversation_id") or (prev.get("summary") or {}).get("conversation_id")
        if cid_raw:
            cid = str(cid_raw)

    if not cid:
        conv = client.conversation_create(
            title="benchmark-10-task-paired",
            agent_id="benchmark-runner",
            metadata={
                "model": "deepseek/deepseek-v4.1-flash",
                "effort": "low",
                "task_count": len(TASKS),
                "search_limit": search_limit,
                "corpus": "symmetric_18_files",
            },
        )
        cid = str(conv.get("conversation_id") or conv.get("id"))

    commandcode_bin = shutil.which("commandcode") or "commandcode"
    cmd = [commandcode_bin, "-p", "-m", "deepseek/deepseek-v4.1-flash", "--no-session", "--effort", "low"]

    for t in TASKS:
        if wanted_ids is not None and t.task_id not in wanted_ids:
            continue
        if t.task_id in completed_by_id:
            print(f"[BENCH {t.task_id}] skipped (already completed in checkpoint)", file=sys.stderr, flush=True)
            continue

        base_prompt = (
            "Engineering Standards and Codebase Reference:\n\n"
            + baseline_ctx
            + f"\n\n### TASK {t.task_id}: {t.title}\n{t.prompt}"
        )
        base_out, base_lat, base_e2e_lat, base_retries, base_timings = _run_cli_with_retry(cmd, base_prompt, timeout_s=timeout_s, max_retries=1, cwd="/tmp")
        base_in_tok = count_tokens(base_prompt)
        base_out_tok = count_tokens(base_out)
        base_ver = verify_task_output(t.verifier_kind, base_out)

        t_search0 = time.perf_counter()
        meko_hits = client.context_search(
            query=t.search_query,
            conversation_id=cid,
            agent_id="benchmark-runner",
            limit=search_limit,
        )
        search_lat = time.perf_counter() - t_search0
        meko_ctx_str = _format_meko_context(meko_hits, max_kb=search_limit)
        meko_prompt = (
            "Retrieved Meko Collective Context (Standards + Codebase + Verified Gotchas):\n\n"
            + meko_ctx_str
            + f"\n\n### TASK {t.task_id}: {t.title}\n{t.prompt}"
        )
        meko_out, meko_llm_lat, meko_e2e_llm_lat, meko_retries, meko_timings = _run_cli_with_retry(cmd, meko_prompt, timeout_s=timeout_s, max_retries=1, cwd="/tmp")
        meko_in_tok = count_tokens(meko_prompt)
        meko_out_tok = count_tokens(meko_out)
        meko_ver = verify_task_output(t.verifier_kind, meko_out)

        client.conversation_add_message(
            conversation_id=cid,
            user_input=f"[{t.task_id}] {t.title}: {t.prompt[:200]}",
            assistant_output=meko_out[:6000],
            agent_id="benchmark-runner",
            reasoning=f"Baseline tokens={base_in_tok+base_out_tok} pass={base_ver['passed']}; Meko tokens={meko_in_tok+meko_out_tok} pass={meko_ver['passed']}",
            metadata={
                "task_id": t.task_id,
                "baseline_total_tokens": base_in_tok + base_out_tok,
                "meko_total_tokens": meko_in_tok + meko_out_tok,
                "baseline_passed": base_ver["passed"],
                "meko_passed": meko_ver["passed"],
            },
        )
        client.track_token_usage(cid, f"bench_{t.task_id}_meko", meko_in_tok, meko_out_tok, model="deepseek-v4.1-flash")

        row = {
            "task_id": t.task_id,
            "title": t.title,
            "baseline": {
                "prompt_tokens": base_in_tok,
                "completion_tokens": base_out_tok,
                "total_tokens": base_in_tok + base_out_tok,
                "latency_s": round(base_lat, 3),
                "end_to_end_latency_s": round(base_e2e_lat, 3),
                "attempt_timings": base_timings,
                "retries": base_retries,
                "reference_cost_usd": _ref_cost_usd(base_in_tok, base_out_tok),
                "passed": base_ver["passed"],
                "rule_violations": base_ver["rule_violations"],
                "violation_count": len(base_ver["rule_violations"]),
                "output_preview": base_out[:4000],
            },
            "meko": {
                "prompt_tokens": meko_in_tok,
                "completion_tokens": meko_out_tok,
                "total_tokens": meko_in_tok + meko_out_tok,
                "search_latency_s": round(search_lat, 3),
                "llm_latency_s": round(meko_llm_lat, 3),
                "end_to_end_llm_latency_s": round(meko_e2e_llm_lat, 3),
                "total_latency_s": round(search_lat + meko_llm_lat, 3),
                "end_to_end_total_latency_s": round(search_lat + meko_e2e_llm_lat, 3),
                "attempt_timings": meko_timings,
                "retries": meko_retries,
                "reference_cost_usd": _ref_cost_usd(meko_in_tok, meko_out_tok),
                "passed": meko_ver["passed"],
                "rule_violations": meko_ver["rule_violations"],
                "violation_count": len(meko_ver["rule_violations"]),
                "output_preview": meko_out[:4000],
            },
        }
        completed_by_id[t.task_id] = row
        ordered_results = [completed_by_id[task.task_id] for task in TASKS if task.task_id in completed_by_id]
        print(
            f"[BENCH {t.task_id}] base=(tok={row['baseline']['total_tokens']}, pass={row['baseline']['passed']}, viol={row['baseline']['violation_count']}, {row['baseline']['latency_s']}s) | "
            f"meko=(tok={row['meko']['total_tokens']}, pass={row['meko']['passed']}, viol={row['meko']['violation_count']}, {row['meko']['total_latency_s']}s)",
            file=sys.stderr,
            flush=True,
        )
        out_path.write_text(
            json.dumps(
                {
                    "partial_tasks": len(ordered_results),
                    "conversation_id": cid,
                    "search_limit": search_limit,
                    "tasks": ordered_results,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    ordered_results = [completed_by_id[task.task_id] for task in TASKS if task.task_id in completed_by_id]
    if len(ordered_results) == len(TASKS):
        summary = _build_benchmark_summary(
            ordered_results,
            baseline_ctx_tokens=baseline_ctx_tokens,
            cid=cid,
            search_limit=search_limit,
        )
        payload = {"summary": summary, "tasks": ordered_results}
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    return {
        "partial_tasks": len(ordered_results),
        "conversation_id": cid,
        "search_limit": search_limit,
        "completed_task_ids": [r["task_id"] for r in ordered_results],
        "tasks": ordered_results,
    }
