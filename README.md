# contextcon-adlc

Shared engineering memory, cross-agent handoff, AMP Postgres 18 zero-copy branch verification, and closed-loop retrieval learning for autonomous coding agents built on Meko Cloud (`meko-cli` + Streamable HTTP MCP v3.2.4).

Submitted for HackerEarth **ContextCon: Remember Everything** under Theme 01 (Coding Agents and ADLC), alongside Theme 07 (2-Minute Auditability) and Theme 08 (10-Task Token Efficiency Benchmark).

- **Live Interactive 2-Minute Audit Portal**: https://contextcon.prince.sh
- **Public GitHub Repository**: https://github.com/princejain756/contextcon-adlc

## Problem

Every isolated coding session starts cold. Developers or agents re-paste architecture docs and source files on every turn, spending 9,000+ prompt tokens repeatedly, while downstream agents (Claude Code, Codex CLI, automated PR reviewers) cannot read the prior agent's reasoning, promoted schema gotchas, or build artifacts without manual copy-paste.

`contextcon-adlc` fixes that by anchoring the entire software delivery lifecycle around a single Meko datapack (`contextcon-adlc`, `56a399c1-e5a5-4027-a5c4-f7d1807c2a41`):

1. **One Shared Memory Across Heterogeneous Agents**: Claude Code on a Mac mini (`claude-code-architect`), Codex CLI on a MacBook Pro (`codex-verifier`), and DeepSeek V4.1 Flash (`pr-review-drift-guard`) collaborate through one Meko `run_id` timeline using `context_search`, `memory_add`, `memory_promote`, `artifact_put`, and `artifact_get`.
2. **Zero-Copy Migration Dry-Runs on AMP Postgres 18**: Before merging schema migrations, an automated verifier provisions a cluster (`adlc-ledger-db`), seeds `main`, forks a copy-on-write branch (`pr-dryrun-1795329172`) at WAL LSN `0/15FBEA8`, verifies idempotent migration execution and `CHECK` constraints on PostgreSQL 18.2, attaches `amp_branch_verification.json`, and deletes compute cleanly down to `0` active vCPUs.
3. **2-Minute Auditability**: Every workflow logs explicit `reasoning`, `plan`, `metadata`, token counts, and artifacts. `export-portal-data` exports all `16` linked conversations (`0` fetch errors), `26` memories, and self-learning telemetry into static JSON.
4. **Closed-Loop Retrieval Self-Learning**: Weak search coverage is detected via `selflearning_status` and `selflearning_shortfalls`, fixed by ingesting `ADR-007` plus promoted memory, and re-verified (`0.3025` low band -> `0.8674` high band).

## Verified Live Results

### 10-Task Paired Benchmark (`deepseek/deepseek-v4.1-flash`, Symmetric 18-File Corpus)

Both arms target the same 18-file fintech `ledger-service` repository (`9,359` tokens across 9 standards docs, 7 Python modules, and 2 SQL migrations) under identical runtime constraints (`--effort low`, `--no-session`, `cwd=/tmp`, `cl100k_base` tokenizer, `$3.00 / 1M` input and `$15.00 / 1M` output reference pricing). Baseline receives all 18 files in prompt context; Meko retrieves the top `6` KB chunks plus up to `3` memories via `context_search`.

| Metric | Baseline (Full Repo Context) | Meko Shared Context (`limit=6`) | Delta |
| --- | ---: | ---: | --- |
| Tasks passed | 9 / 10 | 10 / 10 | +1 task passed |
| Total rule violations | 2 | 0 | -2 violations |
| Prompt tokens (10 tasks) | 94,417 | 9,025 | -90.44% |
| Completion tokens (10 tasks) | 8,414 | 13,917 | +65.40% |
| Total tokens (10 tasks) | 102,831 | 22,942 | -77.69% |
| Avg tokens per task | 10,283.1 | 2,294.2 | -77.69% |
| Reference API cost | $0.409461 | $0.235830 | -42.40% |
| Avg wall latency per task | 25.819s | 51.983s | +101.34% |

See [BENCHMARK_METHODOLOGY.md](BENCHMARK_METHODOLOGY.md) for all 10 per-task measurements and candid notes on why Meko took longer wall time (+101.34%) and why Baseline failed `T10`.

### Live Meko Cloud Verification Summary

| Capability | Live Proof ID / Metric | Verified Outcome |
| --- | --- | --- |
| Symmetric KB Seeding | `19` `.txt` docs (9,068 tokens, `196` chunks) | Symbols preserved (`ROUND_HALF_EVEN`, `hmac.compare_digest`, `v1=`, `Decimal \| str \| int`) |
| Cross-Machine Handoff | `run_id` `aa0058c5affc4a17b857c03705d25df9` across 3 agents | Cross-agent `artifact_get` verified; PR drift guard flagged 5 static + 2 grounded violations |
| AMP Postgres 18 Branching | Cluster `e35a17cf-fa04-4186-a523-24f66c9bb70c` / Fork `pr-dryrun-1795329172` | `cow_inherited_account_rows=1`, LSN `0/15FBEA8`, `0/0.5` vCPU after cleanup |
| Closed-Loop Self-Learning | Query `f1794f9a-c30f-4b92-a2c2-a67408dfee78` (`settlement batch cutoff...`) | `best_score` `0.3025` (`low`) -> `0.8674` (`high`), `hits_above_mid=2` |
| 2-Minute Audit Export | `data/exported_traces.json` & `data/portal_snapshot.json` | `16` traces exported with `0` errors; `26` memories |

## System Flow

```text
  Standards (ADR-001..006, Postmortems, Runbooks) + target_repo (.py/.sql)
                 |  (normalized to plain .txt to preserve backticked symbols)
                 v
     +---------------------------------------------------------------+
     |   Meko Cloud Datapack: contextcon-adlc                        |
     |   - KB (196 chunks)   - Promoted Collective Memory (26 mems)  |
     |   - Artifacts DB      - Self-Learning Query Telemetry         |
     +-------+-----------------------+-----------------------+-------+
             |                       |                       |
             v                       v                       v
  [Agent 1: Mac mini]     [Agent 2: MacBook Pro]  [Agent 3: Drift Guard]
  Claude Code Architect   Codex CLI Verifier      DeepSeek V4.1 Flash
  Drafts 0003 SQL +       Fetches SQL artifact    Checks diff vs ADRs &
  promotes gotcha mem     cross-agent + checks    emits <2min audit JSON
             |                       |
             +-----------+-----------+
                         v
              [AMP Postgres 18 CoW Fork]
              main (LSN 0/15FBEA8) -> fork pr-dryrun -> verify constraints -> delete compute
```

## Quickstart & Reproduction

Prerequisites: Python 3.11+, `uv`, Meko Cloud API key, and (for live LLM/agent steps) `commandcode`, `claude`, and `codex` CLIs.

```bash
cp .env.example .env
# Edit ../.env or .env with MEKO_API_KEY and MEKO_DATAPACK_ID
uv sync

# Run offline unit tests (MCP parser, multipart encoding, verifiers, resume logic)
uv run pytest -q

# Seed symmetric codebase + standards corpus into Meko KB
uv run meko-adlc seed

# Run AMP Postgres 18 zero-copy branch dry-run
uv run meko-adlc amp-check

# Run Agent 2 & Agent 3 cross-machine handoff against an Agent 1 conversation + artifact
uv run meko-adlc handoff-agent23 --conversation-id <cid> --artifact-hash <sha256>

# Run closed-loop self-learning remediation & verification
uv run meko-adlc selflearn

# Run paired 10-task benchmark (resumable in batches)
uv run meko-adlc benchmark --limit 6 --timeout 240 --task-ids T01,T02,T03,T04,T05
uv run meko-adlc benchmark --resume --limit 6 --timeout 240 --task-ids T06,T07,T08,T09,T10

# Export traces, memories, and self-learning stats for portal UI
uv run meko-adlc export-portal-data

# Optional: run the Next.js Live Trace & Audit Portal locally
cd portal && npm install && npm run dev
```

## Repository Map

- `src/meko_adlc/mcp_client.py`: Pure-stdlib Streamable HTTP MCP v3.2.4 client, SSE parser, and ordered S3 presigned multipart uploader.
- `src/meko_adlc/workflows.py`: KB seeding (`.txt` normalization), AMP Postgres 18 zero-copy branch check (`dig` authoritative DNS workaround), 3-agent cross-machine handoff, and self-learning remediation loop.
- `src/meko_adlc/benchmark.py`: Resumable 10-task paired benchmark runner comparing Baseline full-repo context against Meko `context_search`.
- `src/meko_adlc/verifiers.py`: Deterministic AST, regex, SQL, and runtime verifiers plus PR drift auditing.
- `src/meko_adlc/cli.py`: `meko-adlc` CLI entrypoint and `export-portal-data`.
- `target_repo/`: Benchmark fintech `ledger_service` Python modules, SQL migrations, and unit tests.
- `docs/standards/`: Team standards (`ADR-001` through `ADR-006`, `INC-2026-041`, `INC-2026-078`, `SERVICE_CONTRACTS_AND_RUNBOOKS.md`).
- `data/`: Ground-truth JSON captures (`seed_report.json`, `amp_report.json`, `handoff_report.json`, `selflearning_report.json`, `benchmark_results.json`, `exported_traces.json`, `portal_snapshot.json`).
- `portal/`: Next.js 16 + Tailwind CSS v4 interactive audit portal (deployed at https://contextcon.prince.sh).
- `tests/`: Unit test suite (`16 passed`).
- [ARCHITECTURE.md](ARCHITECTURE.md): Protocol internals, AMP branching mechanics, and multi-agent trace design.
- [BENCHMARK_METHODOLOGY.md](BENCHMARK_METHODOLOGY.md): Full 10-task numbers, verifier specs, and limitations.
