"use client";

import { ArrowRight, CheckCircle2, Clock, Database, ExternalLink, GitBranch, Play, Search, ShieldCheck } from "lucide-react";
import {
  formatCount,
  formatPct,
  formatSeconds,
  formatShortTimestamp,
  formatUSD,
} from "@/lib/display-labels";
import { getBenchmarkCompletionTotals, PortalSnapshot } from "@/lib/portal-data";
import type { PortalTabId } from "./PortalShell";

interface OverviewViewProps {
  data: PortalSnapshot;
  onNavigate: (tab: PortalTabId) => void;
  onOpenJudgeBrief: () => void;
  onOpenDemoVideo: () => void;
}

export function OverviewView({ data, onNavigate, onOpenJudgeBrief, onOpenDemoVideo }: OverviewViewProps) {
  const memTotal = data.exported_traces.memories.total;
  const convCount = data.exported_traces.conversations.length;
  const okTraces = data.traces_fetched_ok ?? convCount;
  const errTraces = data.fetch_errors_count ?? 0;
  const summary = data.benchmark_results.summary;
  const tasks = data.benchmark_results.tasks;
  const sl = data.selflearning_report.selflearning_verify;
  const totals = getBenchmarkCompletionTotals(tasks);
  const maxTaskTokens = Math.max(...tasks.map((t) => Math.max(t.baseline.total_tokens, t.meko.total_tokens)), 1);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <span className="pill-neutral type-pill inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5">
            HackerEarth ContextCon Entry
          </span>
          <h1 className="type-page mt-2 text-ink">
            One Shared Memory Across Every Coding Agent
          </h1>
          <p className="type-body mt-1 max-w-2xl text-muted">
            Verified evidence from live Meko Cloud MCP v3.2.4 traces, cross-machine Claude and Codex handoffs, AMP Postgres 18 copy-on-write branching, and a symmetric 10-task benchmark.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={onOpenDemoVideo}
            className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-line-strong bg-surface px-3 py-2 text-xs font-medium text-ink hover:bg-subtle"
          >
            <Play className="h-3.5 w-3.5" />
            Watch 4:13 Demo
          </button>
          <a
            href="https://github.com/princejain756/contextcon-adlc"
            target="_blank"
            rel="noreferrer"
            className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-line-strong bg-surface px-3 py-2 text-xs font-medium text-ink hover:bg-subtle"
          >
            GitHub
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
          <button
            type="button"
            onClick={onOpenJudgeBrief}
            className="inline-flex shrink-0 items-center gap-2 rounded-lg bg-accent px-3.5 py-2 text-xs font-medium text-accent-ink hover:opacity-90"
          >
            2-Minute Audit Brief
            <ArrowRight className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      <section aria-label="Primary metrics" className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
        <div className="app-card p-4">
          <p className="type-kpi-label text-faint">Prompt Token Reduction</p>
          <p className="type-kpi-value numeral mt-1.5 text-ink">
            {formatPct(summary.deltas.prompt_token_reduction_pct)}
          </p>
          <p className="type-meta numeral mt-1 text-muted">
            {formatCount(summary.baseline.prompt_tokens)} to {formatCount(summary.meko.prompt_tokens)} tokens
          </p>
        </div>

        <div className="app-card p-4">
          <p className="type-kpi-label text-faint">Meko Task Pass Rate</p>
          <p className="type-kpi-value numeral mt-1.5 text-ink">
            {summary.meko.passed_count} / {summary.task_count}
          </p>
          <p className="type-meta numeral mt-1 text-muted">
            0 violations vs Baseline {summary.baseline.passed_count} / {summary.task_count} ({summary.baseline.total_violations} viol)
          </p>
        </div>

        <div className="app-card p-4">
          <p className="type-kpi-label text-faint">Reference API Cost Saved</p>
          <p className="type-kpi-value numeral mt-1.5 text-ink">
            {formatPct(summary.deltas.cost_reduction_pct)}
          </p>
          <p className="type-meta numeral mt-1 text-muted">
            {formatUSD(summary.baseline.reference_cost_usd, 4)} to {formatUSD(summary.meko.reference_cost_usd, 4)}
          </p>
        </div>

        <div className="app-card p-4">
          <p className="type-kpi-label text-faint">Self-Learning Uplift</p>
          <p className="type-kpi-value numeral mt-1.5 text-ink">
            {sl.before.best_score.toFixed(2)} to {sl.after.best_score.toFixed(2)}
          </p>
          <p className="type-meta mt-1 text-muted">
            Low band remediated to High ({sl.hits_above_mid} hits)
          </p>
        </div>
      </section>

      <section className="app-card p-4 sm:p-5">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="type-section text-ink">Total Tokens per Task (Baseline vs Meko)</h2>
            <p className="type-meta mt-0.5 text-faint">
              Symmetric 18-file corpus ({formatCount(summary.baseline_repo_context_tokens)} full-repo prompt tokens) on DeepSeek V4.1 Flash.
            </p>
          </div>
          <div className="flex items-center gap-4 text-xs text-muted">
            <span className="inline-flex items-center gap-1.5">
              <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: "var(--bar-baseline)" }} />
              Baseline ({formatCount(summary.baseline.total_tokens)})
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: "var(--bar-meko)" }} />
              Meko ({formatCount(summary.meko.total_tokens)})
            </span>
          </div>
        </div>

        <div className="mt-4 space-y-2.5">
          {tasks.map((t) => {
            const bPct = (t.baseline.total_tokens / maxTaskTokens) * 100;
            const mPct = (t.meko.total_tokens / maxTaskTokens) * 100;
            const totalSaved = (1 - t.meko.total_tokens / t.baseline.total_tokens) * 100;
            return (
              <button
                key={t.task_id}
                type="button"
                onClick={() => onNavigate("benchmark")}
                className="block w-full rounded-lg border border-transparent px-2 py-1.5 text-left transition-colors hover:border-line hover:bg-subtle"
              >
                <div className="flex items-center justify-between gap-2 text-xs">
                  <span className="truncate font-medium text-ink">
                    <span className="font-code text-faint mr-1.5">{t.task_id}</span>
                    {t.title}
                  </span>
                  <span className="numeral shrink-0 font-medium text-muted">
                    {formatCount(t.meko.total_tokens)} vs {formatCount(t.baseline.total_tokens)} (-{totalSaved.toFixed(1)}%)
                  </span>
                </div>
                <div className="mt-1.5 space-y-1">
                  <div className="h-1.5 w-full overflow-hidden rounded-full bg-subtle">
                    <div
                      className="h-full rounded-full"
                      style={{ width: `${bPct}%`, backgroundColor: "var(--bar-baseline)" }}
                    />
                  </div>
                  <div className="h-1.5 w-full overflow-hidden rounded-full bg-subtle">
                    <div
                      className="h-full rounded-full"
                      style={{ width: `${mPct}%`, backgroundColor: "var(--bar-meko)" }}
                    />
                  </div>
                </div>
              </button>
            );
          })}
        </div>

        <div className="mt-4 flex items-start gap-2.5 rounded-lg border border-line bg-subtle p-3">
          <Clock className="mt-0.5 h-4 w-4 shrink-0 text-muted" />
          <p className="type-meta text-muted">
            <strong className="font-medium text-ink">Honest Latency &amp; Proxy Accounting:</strong>{" "}
            Completed-attempt avg increased +{formatPct(summary.deltas.latency_change_pct)} ({formatSeconds(summary.baseline.avg_latency_s, 3)} Baseline vs {formatSeconds(summary.meko.avg_latency_s, 3)} Meko) from {formatSeconds(totals.mekoSearchLatency)} across 10 searches and longer defensive completion outputs ({formatCount(totals.mekoCompletionTokens)} vs {formatCount(totals.baselineCompletionTokens)} completion tokens). Including T10&apos;s 240.0s timeout retry raises Meko lower-bound avg to {formatSeconds(summary.retry_inclusive_lower_bound_avg_s ?? summary.meko.avg_latency_s, 3)} (+{formatPct(summary.retry_inclusive_lower_bound_change_pct ?? summary.deltas.latency_change_pct)}). Counts use local `cl100k_base` text estimates. Total tokens dropped {formatPct(summary.deltas.total_token_reduction_pct)}.
          </p>
        </div>
      </section>

      <section className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <button
          type="button"
          onClick={() => onNavigate("handoff")}
          className="app-card flex items-start justify-between gap-4 p-4 text-left hover:border-line-strong"
        >
          <div>
            <div className="flex items-center gap-2">
              <GitBranch className="h-4 w-4 text-muted" />
              <h3 className="type-section text-ink">3-Agent Cross-Machine Handoff</h3>
            </div>
            <p className="type-body mt-1.5 text-muted">
              Claude Code on Mac mini passed SQL artifact and promoted memory via Meko run ID to Codex CLI and DeepSeek Drift Guard on MacBook Pro.
            </p>
            <p className="type-meta numeral mt-2 text-faint">
              Run {data.handoff_report.run_id.slice(0, 12)}... | {data.handoff_report.agent3_review.findings.length} static + 2 grounded findings
            </p>
          </div>
          <ArrowRight className="mt-1 h-4 w-4 shrink-0 text-faint" />
        </button>

        <button
          type="button"
          onClick={() => onNavigate("amp")}
          className="app-card flex items-start justify-between gap-4 p-4 text-left hover:border-line-strong"
        >
          <div>
            <div className="flex items-center gap-2">
              <Database className="h-4 w-4 text-muted" />
              <h3 className="type-section text-ink">AMP Postgres 18 CoW Fork</h3>
            </div>
            <p className="type-body mt-1.5 text-muted">
              Seeded main at WAL LSN {data.amp_report.main_wal_lsn}, forked zero-copy branch {data.amp_report.fork_branch.name}, verified CHECK constraints, and cleaned down to 0 vCPU.
            </p>
            <p className="type-meta numeral mt-2 text-faint">
              PostgreSQL 18.2 | Inherited rows: {data.amp_report.cow_inherited_account_rows} | Post-run cores: {data.amp_report.amp_core_budget_after.used_cores}
            </p>
          </div>
          <ArrowRight className="mt-1 h-4 w-4 shrink-0 text-faint" />
        </button>

        <button
          type="button"
          onClick={() => onNavigate("amp")}
          className="app-card flex items-start justify-between gap-4 p-4 text-left hover:border-line-strong"
        >
          <div>
            <div className="flex items-center gap-2">
              <Search className="h-4 w-4 text-muted" />
              <h3 className="type-section text-ink">Self-Learning Coverage Loop</h3>
            </div>
            <p className="type-body mt-1.5 text-muted">
              Detected uncovered settlement batch cutoff query at score {sl.before.best_score.toFixed(4)}, ingested ADR-007, and re-verified uplift to {sl.after.best_score.toFixed(4)}.
            </p>
            <p className="type-meta numeral mt-2 text-faint">
              30 tracked searches | 0 zero-results | Avg score {data.exported_traces.selflearning_status.breakdown.totals.avg_score.toFixed(4)}
            </p>
          </div>
          <ArrowRight className="mt-1 h-4 w-4 shrink-0 text-faint" />
        </button>

        <button
          type="button"
          onClick={() => onNavigate("traces")}
          className="app-card flex items-start justify-between gap-4 p-4 text-left hover:border-line-strong"
        >
          <div>
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-muted" />
              <h3 className="type-section text-ink">{convCount} Exported Live Traces & KB</h3>
            </div>
            <p className="type-body mt-1.5 text-muted">
              Browse every conversation turn, explicit agent reasoning, promoted memory, and the {data.seed_report.uploaded.length} plain-text indexed corpus files ({data.seed_report.datapack.knowledge_chunk_count} chunks).
            </p>
            <p className="type-meta numeral mt-2 text-faint">
              <CheckCircle2 className="mr-1 inline h-3.5 w-3.5 text-muted" />
              {okTraces}/{data.traces_attempted ?? convCount} ok ({errTraces} errors) | {memTotal} memories | {formatShortTimestamp(data.exported_at)}
            </p>
          </div>
          <ArrowRight className="mt-1 h-4 w-4 shrink-0 text-faint" />
        </button>
      </section>
    </div>
  );
}
