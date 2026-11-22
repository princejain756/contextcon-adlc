"""CLI entrypoint for contextcon-adlc live Meko workflows and benchmark."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from meko_adlc.benchmark import run_paired_benchmark
from meko_adlc.config import load_config
from meko_adlc.mcp_client import MekoMCPClient
from meko_adlc.workflows import (
    run_amp_branch_check,
    run_handoff_agent1_claude,
    run_handoff_agent23_mbp,
    run_selflearning_loop,
    seed_knowledge_base,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def export_portal_data(client: MekoMCPClient, repo_dir: Path) -> dict:
    data_dir = repo_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    conv = client.conversation_create(title="portal-export-snapshot", agent_id="portal-exporter")
    cid = str(conv.get("conversation_id") or conv.get("id"))

    convs = client.conversation_list(conversation_id=cid, limit=30)
    mems = client.memory_get_all(conversation_id=cid, page=1, page_size=50)
    sl = client.selflearning_status(conversation_id=cid, last="7d")
    dp = client.datapack_describe(conversation_id=cid, include_status=True)

    # Collect (conversation_id, agent_id) from conversation_list AND saved workflow reports
    known_pairs: list[tuple[str, str | None]] = []
    seen_ids: set[str] = {cid}

    conv_items = (convs or {}).get("conversations") or (convs or {}).get("items") or (convs if isinstance(convs, list) else [])
    for c in conv_items:
        if isinstance(c, dict) and (c.get("conversation_id") or c.get("id")):
            tcid = str(c.get("conversation_id") or c.get("id"))
            if tcid not in seen_ids:
                seen_ids.add(tcid)
                known_pairs.append((tcid, str(c["agent_id"]) if c.get("agent_id") else None))

    known_files = [
        ("seed_report.json", "contextcon-seeder"),
        ("amp_report.json", "amp-verifier"),
        ("selflearning_report.json", "selflearning-auditor"),
        ("benchmark_results.json", "benchmark-runner"),
    ]
    snapshot: dict = {}
    for fname, default_agent in known_files:
        p = data_dir / fname
        if p.is_file():
            obj = json.loads(p.read_text(encoding="utf-8"))
            snapshot[fname.replace(".json", "")] = obj
            tcid = obj.get("conversation_id") or (obj.get("summary") or {}).get("conversation_id")
            if tcid and str(tcid) not in seen_ids:
                seen_ids.add(str(tcid))
                known_pairs.append((str(tcid), default_agent))

    hr_path = data_dir / "handoff_report.json"
    if hr_path.is_file():
        hr = json.loads(hr_path.read_text(encoding="utf-8"))
        snapshot["handoff_report"] = hr
        for sub_key in ("agent1_claude", "agent2_codex", "agent3_review"):
            sub = hr.get(sub_key) or {}
            tcid = sub.get("conversation_id")
            tagent = sub.get("agent_id")
            if tcid and str(tcid) not in seen_ids:
                seen_ids.add(str(tcid))
                known_pairs.append((str(tcid), str(tagent) if tagent else None))

    detailed: list[dict] = []
    for tcid, tagent in known_pairs:
        try:
            detailed.append(
                client.conversation_get(
                    tcid,
                    include_messages=True,
                    limit=25,
                    agent_id=tagent,
                )
            )
        except Exception as exc:
            detailed.append({"conversation_id": tcid, "agent_id": tagent, "fetch_note": str(exc)[:200]})

    traces_out = {
        "datapack_name": client.config.datapack_name,
        "datapack_id": client.config.datapack_id,
        "datapack": dp,
        "conversations": detailed,
        "memories": mems,
        "selflearning_status": sl,
    }
    (data_dir / "exported_traces.json").write_text(json.dumps(traces_out, indent=2), encoding="utf-8")

    snapshot["traces_count"] = len(detailed)
    snapshot["exported_traces"] = traces_out
    (data_dir / "portal_snapshot.json").write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    return {"exported_traces_count": len(detailed), "files": sorted(p.name for p in data_dir.glob("*.json"))}


def main() -> None:
    parser = argparse.ArgumentParser(prog="meko-adlc")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_seed = sub.add_parser("seed")
    p_seed.add_argument("--delete-stale-md", action="store_true", default=False)

    sub.add_parser("amp-check")
    p_a1 = sub.add_parser("handoff-agent1")
    p_a1.add_argument("--claude-bin", default="/Users/admin/.local/bin/claude")

    p_a23 = sub.add_parser("handoff-agent23")
    p_a23.add_argument("--conversation-id", required=True)
    p_a23.add_argument("--artifact-hash", required=True)

    sub.add_parser("selflearn")
    p_bench = sub.add_parser("benchmark")
    p_bench.add_argument("--resume", action="store_true", default=False)
    p_bench.add_argument("--task-ids", default="")
    p_bench.add_argument("--limit", type=int, default=6)
    p_bench.add_argument("--timeout", type=float, default=240.0)

    sub.add_parser("export-portal-data")

    args = parser.parse_args()
    repo_dir = _repo_root()
    client = MekoMCPClient(load_config(repo_dir))

    if args.cmd == "seed":
        out = seed_knowledge_base(client, repo_dir, delete_stale_md=args.delete_stale_md)
    elif args.cmd == "amp-check":
        out = run_amp_branch_check(client, repo_dir)
    elif args.cmd == "handoff-agent1":
        out = run_handoff_agent1_claude(client, repo_dir, claude_bin=args.claude_bin)
    elif args.cmd == "handoff-agent23":
        out = run_handoff_agent23_mbp(client, repo_dir, args.conversation_id, args.artifact_hash)
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
        out = export_portal_data(client, repo_dir)
    else:
        raise ValueError(f"Unknown command: {args.cmd}")

    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
