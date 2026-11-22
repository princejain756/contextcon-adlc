"use client";

import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { CheckCircle2, ExternalLink, X } from "lucide-react";
import {
  getClientThemeSnapshot,
  getServerThemeSnapshot,
  subscribeTheme,
} from "@/lib/display-labels";
import { portalData } from "@/lib/portal-data";
import { AmpSelfLearnView } from "./AmpSelfLearnView";
import { BenchmarkView } from "./BenchmarkView";
import { HandoffView } from "./HandoffView";
import { OverviewView } from "./OverviewView";
import { PortalShell, PortalTabId } from "./PortalShell";
import { TracesView } from "./TracesView";

const VALID_TABS: readonly PortalTabId[] = ["overview", "benchmark", "handoff", "amp", "traces"];

function readInitialTab(): PortalTabId {
  if (typeof window === "undefined") return "overview";
  const raw = window.location.hash.replace(/^#/, "") as PortalTabId;
  return VALID_TABS.includes(raw) ? raw : "overview";
}

export function AuditPortal() {
  const [activeTab, setActiveTab] = useState<PortalTabId>(readInitialTab);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [briefOpen, setBriefOpen] = useState(false);
  const [demoOpen, setDemoOpen] = useState(false);
  const briefDialogRef = useRef<HTMLDialogElement>(null);
  const demoDialogRef = useRef<HTMLDialogElement>(null);

  const theme = useSyncExternalStore(
    subscribeTheme,
    getClientThemeSnapshot,
    getServerThemeSnapshot
  );

  useEffect(() => {
    const onHash = () => {
      const next = window.location.hash.replace(/^#/, "") as PortalTabId;
      if (VALID_TABS.includes(next)) {
        setActiveTab(next);
      }
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => {
    const el = briefDialogRef.current;
    if (!el) return;
    if (briefOpen && !el.open) {
      el.showModal();
    } else if (!briefOpen && el.open) {
      el.close();
    }
  }, [briefOpen]);

  useEffect(() => {
    const el = demoDialogRef.current;
    if (!el) return;
    if (demoOpen && !el.open) {
      el.showModal();
    } else if (!demoOpen && el.open) {
      el.close();
    }
  }, [demoOpen]);

  const bSum = portalData.benchmark_results.summary;
  const memTotal = portalData.exported_traces.memories.total;
  const okTraces = portalData.traces_fetched_ok ?? portalData.exported_traces.conversations.length;
  const errTraces = portalData.fetch_errors_count ?? 0;
  const lbAvg = bSum.retry_inclusive_lower_bound_avg_s ?? bSum.meko.avg_latency_s;
  const lbChg = bSum.retry_inclusive_lower_bound_change_pct ?? bSum.deltas.latency_change_pct;

  const handleSelectTab = (tab: PortalTabId) => {
    setActiveTab(tab);
    if (typeof window !== "undefined") {
      window.history.replaceState(null, "", `#${tab}`);
    }
  };

  return (
    <PortalShell
      activeTab={activeTab}
      onSelectTab={handleSelectTab}
      theme={theme}
      mobileOpen={mobileOpen}
      onSetMobileOpen={setMobileOpen}
      onOpenJudgeBrief={() => setBriefOpen(true)}
      onOpenDemoVideo={() => setDemoOpen(true)}
      datapackName={portalData.seed_report.datapack.datapack_name}
    >
      {activeTab === "overview" && (
        <OverviewView
          data={portalData}
          onNavigate={handleSelectTab}
          onOpenJudgeBrief={() => setBriefOpen(true)}
          onOpenDemoVideo={() => setDemoOpen(true)}
        />
      )}
      {activeTab === "benchmark" && (
        <BenchmarkView
          summary={portalData.benchmark_results.summary}
          tasks={portalData.benchmark_results.tasks}
        />
      )}
      {activeTab === "handoff" && <HandoffView handoff={portalData.handoff_report} />}
      {activeTab === "amp" && (
        <AmpSelfLearnView
          amp={portalData.amp_report}
          selflearn={portalData.selflearning_report}
          telemetry={portalData.exported_traces.selflearning_status}
        />
      )}
      {activeTab === "traces" && <TracesView data={portalData} />}

      <dialog
        ref={briefDialogRef}
        onClose={() => setBriefOpen(false)}
        className="m-auto w-[92vw] max-w-2xl rounded-xl border border-line bg-surface p-0 text-ink shadow-xl backdrop:bg-black/50"
      >
        <div className="flex items-center justify-between border-b border-line px-5 py-4">
          <div>
            <p className="type-kpi-label text-faint">ContextCon Judge Verification Guide</p>
            <h2 className="type-drawer text-ink">2-Minute Audit Summary</h2>
          </div>
          <button
            type="button"
            aria-label="Close brief"
            onClick={() => briefDialogRef.current?.close()}
            className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-line bg-subtle text-ink"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-3 px-5 py-4 text-sm text-muted">
          <div className="flex items-start gap-2.5">
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-green-600 dark:text-green-400" />
            <p>
              <strong className="text-ink">Use of Meko (30%):</strong> Single shared datapack ({portalData.seed_report.datapack.knowledge_chunk_count} `.txt` KB chunks, {memTotal} memories), `context_search`, `memory_add`, `memory_promote`, `artifact_put` / `artifact_get`, AMP Postgres 18 CoW fork ({portalData.amp_report.fork_branch.name}), and closed-loop `selflearning_verify` uplift ({portalData.selflearning_report.selflearning_verify.before.best_score.toFixed(4)} to {portalData.selflearning_report.selflearning_verify.after.best_score.toFixed(4)}).
            </p>
          </div>
          <div className="flex items-start gap-2.5">
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-green-600 dark:text-green-400" />
            <p>
              <strong className="text-ink">10-Task Paired Benchmark (cl100k_base proxy):</strong> Meko achieved {bSum.deltas.prompt_token_reduction_pct}% prompt token reduction ({bSum.baseline.prompt_tokens.toLocaleString("en-US")} to {bSum.meko.prompt_tokens.toLocaleString("en-US")}), {bSum.deltas.total_token_reduction_pct}% total token reduction, {bSum.deltas.cost_reduction_pct}% reference API cost savings, and {bSum.meko.passed_count}/{bSum.task_count} pass vs Baseline {bSum.baseline.passed_count}/{bSum.task_count}. Latency tradeoff: {bSum.meko.avg_latency_s}s (+{bSum.deltas.latency_change_pct}%) completed-attempt avg; {lbAvg}s (+{lbChg}%) retry-inclusive lower bound including T10&apos;s 240s timeout retry.
            </p>
          </div>
          <div className="flex items-start gap-2.5">
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-green-600 dark:text-green-400" />
            <p>
              <strong className="text-ink">2-Minute Auditability:</strong> {okTraces} of {portalData.traces_attempted ?? okTraces} conversations exported ({errTraces} fetch errors), explicit agent reasoning, `run_id` linkage across Claude Code (Mac mini), Codex CLI (MacBook Pro), and DeepSeek PR Drift Guard.
            </p>
          </div>
        </div>

        <div className="flex justify-end gap-2 border-t border-line bg-subtle px-5 py-3">
          <button
            type="button"
            onClick={() => briefDialogRef.current?.close()}
            className="rounded-lg bg-accent px-3.5 py-1.5 text-xs font-medium text-accent-ink"
          >
            Done
          </button>
        </div>
      </dialog>

      <dialog
        ref={demoDialogRef}
        onClose={() => setDemoOpen(false)}
        className="m-auto w-[94vw] max-w-3xl rounded-xl border border-line bg-surface p-0 text-ink shadow-xl backdrop:bg-black/60"
      >
        <div className="flex items-center justify-between border-b border-line px-5 py-3.5">
          <div>
            <p className="type-kpi-label text-faint">Unlisted Hackathon Walkthrough (4:13)</p>
            <h2 className="type-drawer text-ink">contextcon-adlc Live Demo Video</h2>
          </div>
          <button
            type="button"
            aria-label="Close demo video"
            onClick={() => demoDialogRef.current?.close()}
            className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-line bg-subtle text-ink"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="p-4 sm:p-5">
          <div className="aspect-video w-full overflow-hidden rounded-lg border border-line bg-black">
            {demoOpen && (
              <iframe
                src="https://www.youtube.com/embed/ApDd1sFDhNs"
                title="contextcon-adlc ContextCon Demo Video"
                className="h-full w-full"
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                allowFullScreen
              />
            )}
          </div>
          <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-muted">
            <span>Walks through Meko KB seeding, 3-agent handoff, AMP Postgres 18 fork, self-learning, and 10-task benchmark.</span>
            <div className="flex items-center gap-3">
              <a
                href="https://youtu.be/ApDd1sFDhNs"
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 font-medium text-ink underline-offset-2 hover:underline"
              >
                Open on YouTube <ExternalLink className="h-3.5 w-3.5" />
              </a>
              <a
                href="https://github.com/princejain756/contextcon-adlc"
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 font-medium text-ink underline-offset-2 hover:underline"
              >
                GitHub Repo <ExternalLink className="h-3.5 w-3.5" />
              </a>
            </div>
          </div>
        </div>
      </dialog>
    </PortalShell>
  );
}
