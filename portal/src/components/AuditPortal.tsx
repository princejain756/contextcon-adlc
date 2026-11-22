"use client";

import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { CheckCircle2, X } from "lucide-react";
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
  const briefDialogRef = useRef<HTMLDialogElement>(null);

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
      datapackName={portalData.seed_report.datapack.datapack_name}
    >
      {activeTab === "overview" && (
        <OverviewView
          data={portalData}
          onNavigate={handleSelectTab}
          onOpenJudgeBrief={() => setBriefOpen(true)}
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
              <strong className="text-ink">Use of Meko (30%):</strong> Single shared datapack ({portalData.seed_report.datapack.knowledge_chunk_count} `.txt` KB chunks, 26 memories), `context_search`, `memory_add`, `memory_promote`, `artifact_put` / `artifact_get`, AMP Postgres 18 CoW fork ({portalData.amp_report.fork_branch.name}), and closed-loop `selflearning_verify` uplift (0.3025 to 0.8674).
            </p>
          </div>
          <div className="flex items-start gap-2.5">
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-green-600 dark:text-green-400" />
            <p>
              <strong className="text-ink">10-Task Paired Benchmark:</strong> Meko achieved 90.44% prompt token reduction (94,417 to 9,025), 77.69% total token reduction, 42.40% reference API cost savings, and 10/10 pass vs Baseline 9/10 (Baseline violated ADR-002.1 and ADR-004.1 on T10). Tradeoff: +101.34% average latency disclosed transparently.
            </p>
          </div>
          <div className="flex items-start gap-2.5">
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-green-600 dark:text-green-400" />
            <p>
              <strong className="text-ink">2-Minute Auditability:</strong> All 16 conversations exported cleanly with 0 errors, explicit agent reasoning, `run_id` linkage across Mac mini and MacBook Pro, and an executive PR rejection brief.
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
    </PortalShell>
  );
}
