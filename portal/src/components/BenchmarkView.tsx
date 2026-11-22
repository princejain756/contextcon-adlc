"use client";

import { useState } from "react";
import { AlertTriangle, CheckCircle2, X } from "lucide-react";
import {
  formatCount,
  formatPct,
  formatSeconds,
  formatUSD,
} from "@/lib/display-labels";
import type { BenchmarkSummary, BenchmarkTaskRow } from "@/lib/portal-data";

interface BenchmarkViewProps {
  summary: BenchmarkSummary;
  tasks: BenchmarkTaskRow[];
}

type FilterMode = "all" | "both_pass" | "base_fail";

export function BenchmarkView({ summary, tasks }: BenchmarkViewProps) {
  const [filter, setFilter] = useState<FilterMode>("all");
  const [selectedTaskId, setSelectedTaskId] = useState<string>("T10");

  const filtered = tasks.filter((t) => {
    if (filter === "both_pass") return t.baseline.passed && t.meko.passed;
    if (filter === "base_fail") return !t.baseline.passed;
    return true;
  });

  const selected = tasks.find((t) => t.task_id === selectedTaskId) ?? tasks[0];

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="type-page text-ink">10-Task Paired Benchmark</h1>
          <p className="type-body mt-1 text-muted">
            Symmetric 18-file codebase corpus ({formatCount(summary.baseline_repo_context_tokens)} prompt tokens) evaluated with deterministic AST, SQL, and runtime verifiers.
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {[
            { id: "all" as const, label: `All (${tasks.length})` },
            { id: "both_pass" as const, label: "Both Passed (9)" },
            { id: "base_fail" as const, label: "Baseline Failed (1)" },
          ].map((btn) => (
            <button
              key={btn.id}
              type="button"
              onClick={() => setFilter(btn.id)}
              className={`type-pill rounded-full px-3 py-1 transition-colors ${
                filter === btn.id
                  ? "bg-accent text-accent-ink"
                  : "pill-neutral hover:bg-rail-hover"
              }`}
            >
              {btn.label}
            </button>
          ))}
        </div>
      </div>

      <div className="app-card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left">
            <thead>
              <tr className="border-b border-line bg-subtle text-faint">
                <th className="type-table-head px-3 py-2.5">Task</th>
                <th className="type-table-head px-3 py-2.5 text-right">Base In</th>
                <th className="type-table-head px-3 py-2.5 text-right">Meko In</th>
                <th className="type-table-head px-3 py-2.5 text-right">Base Tot</th>
                <th className="type-table-head px-3 py-2.5 text-right">Meko Tot</th>
                <th className="type-table-head px-3 py-2.5 text-right">Saved</th>
                <th className="type-table-head px-3 py-2.5 text-right">Base Cost</th>
                <th className="type-table-head px-3 py-2.5 text-right">Meko Cost</th>
                <th className="type-table-head px-3 py-2.5 text-right">Time (B / M)</th>
                <th className="type-table-head px-3 py-2.5">Verdicts</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((t) => {
                const saved = (1 - t.meko.total_tokens / t.baseline.total_tokens) * 100;
                const active = selected?.task_id === t.task_id;
                return (
                  <tr
                    key={t.task_id}
                    onClick={() => setSelectedTaskId(t.task_id)}
                    className={`cursor-pointer border-b border-line transition-colors ${
                      active ? "bg-subtle" : "hover:bg-subtle/60"
                    }`}
                  >
                    <td className="type-table-cell px-3 py-2.5">
                      <span className="font-code font-medium text-ink mr-1.5">{t.task_id}</span>
                      <span className="text-muted">{t.title}</span>
                    </td>
                    <td className="type-table-cell numeral px-3 py-2.5 text-right text-muted">
                      {formatCount(t.baseline.prompt_tokens)}
                    </td>
                    <td className="type-table-cell numeral px-3 py-2.5 text-right font-medium text-ink">
                      {formatCount(t.meko.prompt_tokens)}
                    </td>
                    <td className="type-table-cell numeral px-3 py-2.5 text-right text-muted">
                      {formatCount(t.baseline.total_tokens)}
                    </td>
                    <td className="type-table-cell numeral px-3 py-2.5 text-right font-medium text-ink">
                      {formatCount(t.meko.total_tokens)}
                    </td>
                    <td className="type-table-cell numeral px-3 py-2.5 text-right text-ink">
                      {formatPct(saved, 1)}
                    </td>
                    <td className="type-table-cell numeral px-3 py-2.5 text-right text-muted">
                      {formatUSD(t.baseline.reference_cost_usd, 4)}
                    </td>
                    <td className="type-table-cell numeral px-3 py-2.5 text-right text-ink">
                      {formatUSD(t.meko.reference_cost_usd, 4)}
                    </td>
                    <td className="type-table-cell numeral px-3 py-2.5 text-right text-muted">
                      {formatSeconds(t.baseline.latency_s ?? 0, 1)} / {formatSeconds(t.meko.total_latency_s ?? 0, 1)}
                    </td>
                    <td className="type-table-cell px-3 py-2.5">
                      <div className="flex items-center gap-1.5">
                        <span
                          className={`type-pill rounded px-1.5 py-0.5 ${
                            t.baseline.passed ? "pill-neutral" : "pill-danger"
                          }`}
                        >
                          B: {t.baseline.passed ? "Pass" : `Fail (${t.baseline.violation_count})`}
                        </span>
                        <span
                          className={`type-pill rounded px-1.5 py-0.5 ${
                            t.meko.passed ? "pill-success" : "pill-danger"
                          }`}
                        >
                          M: {t.meko.passed ? "Pass" : `Fail (${t.meko.violation_count})`}
                        </span>
                      </div>
                    </td>
                  </tr>
                );
              })}
              <tr className="bg-subtle font-medium text-ink">
                <td className="type-table-cell px-3 py-2.5">10-Task Aggregate</td>
                <td className="type-table-cell numeral px-3 py-2.5 text-right">
                  {formatCount(summary.baseline.prompt_tokens)}
                </td>
                <td className="type-table-cell numeral px-3 py-2.5 text-right">
                  {formatCount(summary.meko.prompt_tokens)}
                </td>
                <td className="type-table-cell numeral px-3 py-2.5 text-right">
                  {formatCount(summary.baseline.total_tokens)}
                </td>
                <td className="type-table-cell numeral px-3 py-2.5 text-right">
                  {formatCount(summary.meko.total_tokens)}
                </td>
                <td className="type-table-cell numeral px-3 py-2.5 text-right">
                  {formatPct(summary.deltas.total_token_reduction_pct)}
                </td>
                <td className="type-table-cell numeral px-3 py-2.5 text-right">
                  {formatUSD(summary.baseline.reference_cost_usd, 4)}
                </td>
                <td className="type-table-cell numeral px-3 py-2.5 text-right">
                  {formatUSD(summary.meko.reference_cost_usd, 4)}
                </td>
                <td className="type-table-cell numeral px-3 py-2.5 text-right">
                  {formatSeconds(summary.baseline.avg_latency_s, 1)} / {formatSeconds(summary.meko.avg_latency_s, 1)} avg ({formatSeconds(summary.retry_inclusive_lower_bound_avg_s ?? summary.meko.avg_latency_s, 1)} w/ retry)
                </td>
                <td className="type-table-cell px-3 py-2.5">
                  {summary.baseline.passed_count}/{summary.task_count} vs {summary.meko.passed_count}/{summary.task_count}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        {summary.timing_note && (
          <div className="border-t border-line bg-subtle px-3.5 py-2.5">
            <p className="type-meta text-muted">
              <strong className="text-ink">Timing &amp; Token Proxy Note:</strong> {summary.timing_note} Tokens counted via local `{summary.tokenizer}` proxy using reference rates ({summary.reference_pricing}).
            </p>
          </div>
        )}
      </div>

      {selected && (
        <section className="app-card p-4 sm:p-5">
          <div className="flex flex-wrap items-start justify-between gap-2 border-b border-line pb-3">
            <div>
              <p className="type-kpi-label text-faint">Selected Task Output & Rule Inspection</p>
              <h2 className="type-section mt-0.5 text-ink">
                <span className="font-code mr-1.5">{selected.task_id}</span>
                {selected.title}
              </h2>
            </div>
            <div className="flex items-center gap-2">
              <span className="pill-neutral type-pill rounded-full px-2.5 py-0.5">
                Search latency {formatSeconds(selected.meko.search_latency_s ?? 0)}
              </span>
              {(selected.meko.retries ?? 0) > 0 && (
                <span className="pill-warning type-pill rounded-full px-2.5 py-0.5">
                  Retries: {selected.meko.retries}
                </span>
              )}
              <button
                type="button"
                aria-label="Clear task filter"
                onClick={() => setFilter("all")}
                className="inline-flex items-center gap-1 rounded-md border border-line px-2 py-1 text-xs text-muted hover:bg-subtle lg:hidden"
              >
                <X className="h-3 w-3" /> Reset
              </button>
            </div>
          </div>

          <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="rounded-lg border border-line bg-subtle p-3.5">
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-semibold text-ink">Baseline Arm</span>
                <span
                  className={`type-pill inline-flex items-center gap-1 rounded-full px-2 py-0.5 ${
                    selected.baseline.passed ? "pill-success" : "pill-danger"
                  }`}
                >
                  {selected.baseline.passed ? (
                    <CheckCircle2 className="h-3 w-3" />
                  ) : (
                    <AlertTriangle className="h-3 w-3" />
                  )}
                  {selected.baseline.passed ? "Passed" : `Failed (${selected.baseline.violation_count} violations)`}
                </span>
              </div>
              <p className="type-meta numeral mt-1 text-faint">
                Prompt {formatCount(selected.baseline.prompt_tokens)} | Completion {formatCount(selected.baseline.completion_tokens)} | Total {formatCount(selected.baseline.total_tokens)} tokens
              </p>
              {selected.baseline.rule_violations.length > 0 && (
                <ul className="mt-2.5 space-y-1 rounded-md border border-line bg-surface p-2.5 text-xs text-ink">
                  {selected.baseline.rule_violations.map((v, i) => (
                    <li key={i} className="flex items-start gap-1.5">
                      <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-red-600 dark:text-red-400" />
                      <span>{v}</span>
                    </li>
                  ))}
                  {selected.task_id === "T10" && (
                    <li className="type-meta pt-1 text-muted">
                      Root cause: seeing all target modules, Baseline imported helpers instead of emitting self-contained Decimal ROUND_HALF_EVEN and PII redaction logic inside the single handler file.
                    </li>
                  )}
                </ul>
              )}
              <pre className="font-code mt-2.5 max-h-64 overflow-auto rounded-md border border-line bg-surface p-3 text-[11px] leading-relaxed text-ink">
                {selected.baseline.output_preview}
              </pre>
            </div>

            <div className="rounded-lg border border-line bg-subtle p-3.5">
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-semibold text-ink">Meko Shared Context Arm</span>
                <span
                  className={`type-pill inline-flex items-center gap-1 rounded-full px-2 py-0.5 ${
                    selected.meko.passed ? "pill-success" : "pill-danger"
                  }`}
                >
                  {selected.meko.passed ? (
                    <CheckCircle2 className="h-3 w-3" />
                  ) : (
                    <AlertTriangle className="h-3 w-3" />
                  )}
                  {selected.meko.passed ? "Passed (0 violations)" : "Failed"}
                </span>
              </div>
              <p className="type-meta numeral mt-1 text-faint">
                Prompt {formatCount(selected.meko.prompt_tokens)} | Completion {formatCount(selected.meko.completion_tokens)} | Total {formatCount(selected.meko.total_tokens)} tokens
              </p>
              <pre className="font-code mt-2.5 max-h-64 overflow-auto rounded-md border border-line bg-surface p-3 text-[11px] leading-relaxed text-ink">
                {selected.meko.output_preview}
              </pre>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
