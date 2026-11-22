"""CLI entrypoint for contextcon-adlc live Meko workflows, offline audit checks, and benchmark."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import sys
from typing import Any

from meko_adlc.benchmark import run_paired_benchmark
from meko_adlc.config import load_config
from meko_adlc.mcp_client import MekoMCPClient
from meko_adlc.workflows import (
    run_amp_branch_check,
    run_handoff_agent1_claude,
    run_handoff_agent23_mbp,
    run_selflearning_loop,
    sanitize_public_report,
    seed_knowledge_base,
)

_SECRET_SCAN_RE = re.compile(
    r"(X-Amz-(?:Algorithm|Credential|Signature|Security-Token|Date|Checksum-Sha256)"
    r"|AKIA[0-9A-Z]{16}"
    r'|"(?:upload_fields|upload_url|presigned_url)"'
    r'|"(?:policy)"\s*:\s*"eyJ'
    r"|mko_[A-Za-z0-9_-]{12,}"
    r"|MEKO_AMP_ADMIN_PW\s*=)"
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _count_trace_outcomes(conversations: list[Any]) -> tuple[int, int, int]:
    attempted = len(conversations)
    errors = sum(
        1 for c in conversations if isinstance(c, dict) and ("fetch_note" in c or "error" in c)
    )
    return attempted, attempted - errors, errors


def _collect_memories_paginated(client: MekoMCPClient, cid: str, page_size: int = 50) -> dict[str, Any]:
    all_items: list[Any] = []
    last_payload: dict[str, Any] = {}
    list_key = "memories"
    page = 1
    while page <= 20:
        res = client.memory_get_all(conversation_id=cid, page=page, page_size=page_size)
        if not isinstance(res, dict):
            break
        last_payload = res
        batch: list[Any] = []
        for k in ("memories", "results", "items"):
            if isinstance(res.get(k), list):
                list_key = k
                batch = res[k]
                break
        if not batch:
            break
        all_items.extend(batch)
        if len(batch) < page_size:
            break
        page += 1
    out = dict(last_payload)
    if all_items:
        out[list_key] = all_items
    return out


def export_portal_data(
    client: MekoMCPClient | None,
    repo_dir: Path,
    *,
    rebuild_snapshot_only: bool = False,
) -> dict[str, Any]:
    data_dir = repo_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    exported_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    known_files = [
        ("seed_report.json", "contextcon-seeder"),
        ("amp_report.json", "amp-verifier"),
        ("selflearning_report.json", "selflearning-auditor"),
        ("benchmark_results.json", "benchmark-runner"),
    ]
    snapshot: dict[str, Any] = {}
    known_pairs: list[tuple[str, str | None]] = []
    seen_ids: set[str] = set()

    for fname, default_agent in known_files:
        p = data_dir / fname
        if p.is_file():
            obj = sanitize_public_report(json.loads(p.read_text(encoding="utf-8")))
            snapshot[fname.replace(".json", "")] = obj
            tcid = obj.get("conversation_id") or (obj.get("summary") or {}).get("conversation_id")
            if tcid and str(tcid) not in seen_ids:
                seen_ids.add(str(tcid))
                known_pairs.append((str(tcid), default_agent))

    hr_path = data_dir / "handoff_report.json"
    if hr_path.is_file():
        hr = sanitize_public_report(json.loads(hr_path.read_text(encoding="utf-8")))
        snapshot["handoff_report"] = hr
        for sub_key in ("agent1_claude", "agent2_codex", "agent3_review"):
            sub = hr.get(sub_key) or {}
            tcid = sub.get("conversation_id")
            tagent = sub.get("agent_id")
            if tcid and str(tcid) not in seen_ids:
                seen_ids.add(str(tcid))
                known_pairs.append((str(tcid), str(tagent) if tagent else None))

    if rebuild_snapshot_only:
        traces_path = data_dir / "exported_traces.json"
        if not traces_path.is_file():
            raise FileNotFoundError(f"Missing {traces_path} for --rebuild-snapshot-only")
        traces_out = sanitize_public_report(json.loads(traces_path.read_text(encoding="utf-8")))
        if not isinstance(traces_out, dict):
            raise ValueError("exported_traces.json must be a JSON object")
        conversations = list(traces_out.get("conversations") or [])
        attempted, ok_count, err_count = _count_trace_outcomes(conversations)
        traces_out["exported_at"] = traces_out.get("exported_at") or exported_at
        traces_out["snapshot_rebuilt_at"] = exported_at
        traces_out["traces_attempted"] = attempted
        traces_out["traces_fetched_ok"] = ok_count
        traces_out["fetch_errors_count"] = err_count
        traces_path.write_text(json.dumps(traces_out, indent=2), encoding="utf-8")
    else:
        assert client is not None
        conv = client.conversation_create(title="portal-export-snapshot", agent_id="portal-exporter")
        cid = str(conv.get("conversation_id") or conv.get("id"))
        seen_ids.add(cid)

        convs = client.conversation_list(conversation_id=cid, limit=30)
        mems = sanitize_public_report(_collect_memories_paginated(client, cid, page_size=50))
        sl = sanitize_public_report(client.selflearning_status(conversation_id=cid, last="7d"))
        dp = sanitize_public_report(client.datapack_describe(conversation_id=cid, include_status=True))

        conv_items = (convs or {}).get("conversations") or (convs or {}).get("items") or (convs if isinstance(convs, list) else [])
        list_pairs: list[tuple[str, str | None]] = []
        list_seen: set[str] = {cid}
        for c in conv_items:
            if isinstance(c, dict) and (c.get("conversation_id") or c.get("id")):
                tcid = str(c.get("conversation_id") or c.get("id"))
                if tcid not in list_seen:
                    list_seen.add(tcid)
                    list_pairs.append((tcid, str(c["agent_id"]) if c.get("agent_id") else None))
        for tcid, tagent in known_pairs:
            if tcid not in list_seen:
                list_seen.add(tcid)
                list_pairs.append((tcid, tagent))

        detailed: list[dict[str, Any]] = []
        for tcid, tagent in list_pairs:
            try:
                detailed.append(
                    sanitize_public_report(
                        client.conversation_get(
                            tcid,
                            include_messages=True,
                            limit=25,
                            agent_id=tagent,
                        )
                    )
                )
            except Exception as exc:
                detailed.append({"conversation_id": tcid, "agent_id": tagent, "fetch_note": str(exc)[:200]})

        attempted, ok_count, err_count = _count_trace_outcomes(detailed)
        traces_out = sanitize_public_report({
            "exported_at": exported_at,
            "datapack_name": client.config.datapack_name,
            "datapack_id": client.config.datapack_id,
            "datapack": dp,
            "traces_attempted": attempted,
            "traces_fetched_ok": ok_count,
            "fetch_errors_count": err_count,
            "conversations": detailed,
            "memories": mems,
            "selflearning_status": sl,
        })
        (data_dir / "exported_traces.json").write_text(json.dumps(traces_out, indent=2), encoding="utf-8")

    snapshot["exported_at"] = traces_out.get("exported_at") or exported_at
    snapshot["traces_count"] = len(traces_out.get("conversations") or [])
    snapshot["traces_attempted"] = traces_out.get("traces_attempted", snapshot["traces_count"])
    snapshot["traces_fetched_ok"] = traces_out.get("traces_fetched_ok", snapshot["traces_count"])
    snapshot["fetch_errors_count"] = traces_out.get("fetch_errors_count", 0)
    snapshot["exported_traces"] = traces_out
    safe_snapshot = sanitize_public_report(snapshot)
    (data_dir / "portal_snapshot.json").write_text(json.dumps(safe_snapshot, indent=2), encoding="utf-8")
    return {
        "exported_traces_count": snapshot["traces_count"],
        "traces_fetched_ok": snapshot["traces_fetched_ok"],
        "fetch_errors_count": snapshot["fetch_errors_count"],
        "rebuild_snapshot_only": rebuild_snapshot_only,
        "files": sorted(p.name for p in data_dir.glob("*.json")),
    }


def run_doctor(repo_dir: Path) -> tuple[dict[str, Any], int]:
    """Offline check for JSON integrity, snapshot parity, secret/S3 leakage, and optional CLIs."""
    data_dir = repo_dir / "data"
    portal_snap = repo_dir / "portal" / "src" / "data" / "portal_snapshot.json"
    required = [
        "seed_report.json",
        "amp_report.json",
        "handoff_report.json",
        "selflearning_report.json",
        "benchmark_results.json",
        "exported_traces.json",
        "portal_snapshot.json",
    ]
    missing = [name for name in required if not (data_dir / name).is_file()]
    parse_errors: list[str] = []
    secret_leaks: list[str] = []

    scan_paths = sorted(data_dir.glob("*.json"))
    if portal_snap.is_file():
        scan_paths.append(portal_snap)

    for p in scan_paths:
        txt = p.read_text(encoding="utf-8")
        try:
            json.loads(txt)
        except Exception as exc:
            parse_errors.append(f"{p.relative_to(repo_dir)}: {exc}")
        m = _SECRET_SCAN_RE.search(txt)
        if m:
            secret_leaks.append(f"{p.relative_to(repo_dir)}: matched {m.group(0)[:40]}")

    snap_equal = False
    if (data_dir / "portal_snapshot.json").is_file() and portal_snap.is_file():
        snap_equal = (
            (data_dir / "portal_snapshot.json").read_bytes() == portal_snap.read_bytes()
        )

    optional_tools = {
        tool: bool(shutil.which(tool))
        for tool in ("claude", "codex", "commandcode", "dig", "node")
    }
    ok = (not missing) and (not parse_errors) and (not secret_leaks) and snap_equal
    return {
        "ok": ok,
        "offline_judge_ready": ok,
        "missing_files": missing,
        "parse_errors": parse_errors,
        "secret_leaks": secret_leaks,
        "portal_snapshot_in_sync": snap_equal,
        "optional_live_clis": optional_tools,
    }, (0 if ok else 1)


def run_replay_audit(repo_dir: Path) -> str:
    """Print an offline 2-minute judge audit replay from sanitized captured runs."""
    data_dir = repo_dir / "data"
    snap = json.loads((data_dir / "portal_snapshot.json").read_text(encoding="utf-8"))
    hr = snap.get("handoff_report") or {}
    amp = snap.get("amp_report") or {}
    sl = snap.get("selflearning_report") or {}
    br = snap.get("benchmark_results") or {}
    ex = snap.get("exported_traces") or {}
    bsum = br.get("summary") or {}

    a1 = hr.get("agent1_claude") or {}
    a2 = hr.get("agent2_codex") or {}
    a3 = hr.get("agent3_review") or {}
    base = bsum.get("baseline") or {}
    meko = bsum.get("meko") or {}
    deltas = bsum.get("deltas") or {}
    vblock = sl.get("selflearning_verify") or {}
    vb = vblock.get("before") or {}
    va = vblock.get("after") or {}
    before_score = vb.get("best_score", vblock.get("before_best_score"))
    before_band = vb.get("band", vblock.get("before_band"))
    after_score = va.get("best_score", vblock.get("after_best_score"))
    after_band = va.get("band", vblock.get("after_band"))
    sl_after = sl.get("status_after") or {}
    sl_after_q = sl_after.get("quality") or {}
    sl_after_tot = (sl_after.get("breakdown") or {}).get("totals") or {}
    sl_ex = ex.get("selflearning_status") or {}
    sl_ex_q = sl_ex.get("quality") or {}
    sl_ex_tot = (sl_ex.get("breakdown") or {}).get("totals") or {}

    lines = [
        "=== CONTEXTCON-ADLC: OFFLINE AUDIT REPLAY OF CAPTURED RUNS ===",
        f"Datapack: {ex.get('datapack_name')} ({ex.get('datapack_id')})",
        f"Snapshot Exported At: {snap.get('exported_at', 'unknown')} | Conversations: {snap.get('traces_fetched_ok')}/{snap.get('traces_attempted')} ok (errors={snap.get('fetch_errors_count', 0)})",
        "",
        "[1] Cross-Machine 3-Agent Handoff",
        f"  run_id: {hr.get('run_id')}",
        f"  Agent 1 ({a1.get('agent_id')}): provenance={a1.get('provenance')} | memories={a1.get('memory_ids')} | artifact={a1.get('artifact_hash')}",
        f"  Agent 2 ({a2.get('agent_id')}): conv={a2.get('conversation_id')} | access={a2.get('artifact_access_mode')} | sql_passed={(a2.get('sql_check') or {}).get('passed')}",
        f"  Agent 3 ({a3.get('agent_id')}): conv={a3.get('conversation_id')} | static_findings={len(a3.get('findings') or [])}",
        "",
        "[2] AMP Postgres 18 Zero-Copy CoW Branching",
        f"  Cluster: {amp.get('cluster_id')} | Fork: {(amp.get('fork_branch') or {}).get('name')} | LSN: {amp.get('main_wal_lsn')}",
        f"  Rows inherited: {amp.get('cow_inherited_account_rows')} | Negative CHECK rejected: {amp.get('negative_amount_check_violation_enforced')} | Status: {amp.get('status')}",
        "",
        "[3] Closed-Loop Self-Learning (Distinct Scopes)",
        f"  Single query replay (settlement cutoff): {before_score} ({before_band}) -> {after_score} ({after_band}), hits_above_mid={vblock.get('hits_above_mid')}",
        f"  Immediate status_after window: searches={sl_after_q.get('searches')}, high={sl_after_q.get('high')}, avg_score={sl_after_tot.get('avg_score')}, quality_pct={sl_after_q.get('pct')}%",
        f"  7d Exported Telemetry Aggregate: searches={sl_ex_q.get('searches')}, zero_results={sl_ex_tot.get('zero_results')}, high={sl_ex_q.get('high')}, avg_score={sl_ex_tot.get('avg_score')}, quality_pct={sl_ex_q.get('pct')}%",
        "",
        "[4] 10-Task Paired Benchmark (deepseek/deepseek-v4.1-flash, cl100k_base proxy)",
        f"  Baseline: {base.get('passed_count')}/10 passed, {base.get('total_violations')} violations, {base.get('prompt_tokens')} prompt tok, {base.get('total_tokens')} total tok, ${base.get('reference_cost_usd')}, avg {base.get('avg_latency_s')}s",
        f"  Meko:     {meko.get('passed_count')}/10 passed, {meko.get('total_violations')} violations, {meko.get('prompt_tokens')} prompt tok, {meko.get('total_tokens')} total tok, ${meko.get('reference_cost_usd')}",
        f"  Meko Latency: completed_attempt_avg={meko.get('avg_latency_s')}s (+{deltas.get('latency_change_pct')}%), retry_inclusive_lower_bound={bsum.get('retry_inclusive_lower_bound_avg_s')}s (+{bsum.get('retry_inclusive_lower_bound_change_pct')}% incl. T10 240s retry)",
        f"  Reductions: {deltas.get('prompt_token_reduction_pct')}% prompt tokens, {deltas.get('total_token_reduction_pct')}% total tokens, {deltas.get('cost_reduction_pct')}% reference cost",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(prog="meko-adlc")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("doctor", help="Offline check for JSON integrity, snapshot parity, secrets, and local tools")
    sub.add_parser("replay-audit", help="Print offline 2-minute judge replay from sanitized captured runs")

    p_seed = sub.add_parser("seed")
    p_seed.add_argument("--delete-stale-md", action="store_true", default=False)

    p_amp = sub.add_parser("amp-check")
    p_amp.add_argument("--recreate-if-missing-pw", action="store_true", default=False)
    p_amp.add_argument("--write-env", action="store_true", default=False)

    p_a1 = sub.add_parser("handoff-agent1")
    p_a1.add_argument("--claude-bin", default=None)

    p_a23 = sub.add_parser("handoff-agent23")
    p_a23.add_argument("--conversation-id", required=True)
    p_a23.add_argument("--artifact-hash", required=True)
    p_a23.add_argument("--agent1-report", default=None)

    sub.add_parser("selflearn")
    p_bench = sub.add_parser("benchmark")
    p_bench.add_argument("--resume", action="store_true", default=False)
    p_bench.add_argument("--task-ids", default="")
    p_bench.add_argument("--limit", type=int, default=6)
    p_bench.add_argument("--timeout", type=float, default=240.0)

    p_exp = sub.add_parser("export-portal-data")
    p_exp.add_argument("--rebuild-snapshot-only", action="store_true", default=False)

    args = parser.parse_args()
    repo_dir = _repo_root()

    if args.cmd == "doctor":
        doc_out, rc = run_doctor(repo_dir)
        print(json.dumps(doc_out, indent=2))
        sys.exit(rc)

    if args.cmd == "replay-audit":
        print(run_replay_audit(repo_dir))
        return

    if args.cmd == "export-portal-data" and args.rebuild_snapshot_only:
        out = export_portal_data(None, repo_dir, rebuild_snapshot_only=True)
        print(json.dumps(out, indent=2))
        return

    client = MekoMCPClient(load_config(repo_dir))

    if args.cmd == "seed":
        out = seed_knowledge_base(client, repo_dir, delete_stale_md=args.delete_stale_md)
    elif args.cmd == "amp-check":
        out = run_amp_branch_check(
            client,
            repo_dir,
            recreate_if_missing_pw=args.recreate_if_missing_pw,
            write_env=args.write_env,
        )
        print(json.dumps(out, indent=2))
        if not out.get("verified"):
            sys.exit(1)
        return
    elif args.cmd == "handoff-agent1":
        out = run_handoff_agent1_claude(client, repo_dir, claude_bin=args.claude_bin)
    elif args.cmd == "handoff-agent23":
        a1_path = Path(args.agent1_report) if args.agent1_report else None
        out = run_handoff_agent23_mbp(
            client,
            repo_dir,
            args.conversation_id,
            args.artifact_hash,
            agent1_report_path=a1_path,
        )
    elif args.cmd == "selflearn":
        out = run_selflearning_loop(client, repo_dir)
    elif args.cmd == "benchmark":
        parsed_task_ids = [s.strip() for s in args.task_ids.split(",") if s.strip()] or None
        out = run_paired_benchmark(
            client,
            repo_dir,
            resume=args.resume,
            task_ids=parsed_task_ids,
            search_limit=args.limit,
            timeout_s=args.timeout,
        )
    elif args.cmd == "export-portal-data":
        out = export_portal_data(client, repo_dir, rebuild_snapshot_only=False)
    else:
        raise ValueError(f"Unknown command: {args.cmd}")

    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
