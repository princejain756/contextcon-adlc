"use client";

import { useEffect, useRef } from "react";
import {
  Activity,
  BarChart3,
  Database,
  ExternalLink,
  FileSearch,
  GitBranch,
  Layers,
  Menu,
  Moon,
  Sun,
  X,
} from "lucide-react";
import { applyThemeWithoutFreeze } from "@/lib/display-labels";

export type PortalTabId = "overview" | "benchmark" | "handoff" | "amp" | "traces";

export const NAV_ITEMS: ReadonlyArray<{
  id: PortalTabId;
  label: string;
  meta: string;
  icon: typeof Layers;
}> = [
  { id: "overview", label: "Overview", meta: "Summary", icon: Layers },
  { id: "benchmark", label: "10-Task Benchmark", meta: "90.4%", icon: BarChart3 },
  { id: "handoff", label: "Agent Handoff", meta: "3 agents", icon: GitBranch },
  { id: "amp", label: "AMP & Self-Learning", meta: "PG18", icon: Database },
  { id: "traces", label: "Traces & KB", meta: "16 runs", icon: FileSearch },
];

interface PortalShellProps {
  activeTab: PortalTabId;
  onSelectTab: (tab: PortalTabId) => void;
  theme: "light" | "dark";
  mobileOpen: boolean;
  onSetMobileOpen: (open: boolean) => void;
  onOpenJudgeBrief: () => void;
  datapackName: string;
  children: React.ReactNode;
}

export function PortalShell({
  activeTab,
  onSelectTab,
  theme,
  mobileOpen,
  onSetMobileOpen,
  onOpenJudgeBrief,
  datapackName,
  children,
}: PortalShellProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const el = dialogRef.current;
    if (!el) return;
    if (mobileOpen && !el.open) {
      el.showModal();
    } else if (!mobileOpen && el.open) {
      el.close();
    }
  }, [mobileOpen]);

  const handleTabClick = (tab: PortalTabId) => {
    onSelectTab(tab);
    dialogRef.current?.close();
  };

  const renderRailContent = () => (
    <div className="flex h-full flex-col justify-between">
      <div className="min-h-0 flex-1 overflow-y-auto app-rail-scroll px-3 pt-4 pb-3">
        <div className="mb-4 px-2.5">
          <div className="flex items-center justify-between gap-2">
            <span className="font-code text-xs font-semibold tracking-tight text-ink">
              contextcon-adlc
            </span>
            <span className="pill-success type-pill inline-flex items-center rounded-full px-2 py-0.5">
              Live
            </span>
          </div>
          <p className="type-meta mt-1 text-faint">Meko Cloud ADLC Audit Portal</p>
        </div>

        <nav aria-label="Primary navigation" className="space-y-1">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const active = activeTab === item.id;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => handleTabClick(item.id)}
                className={`flex w-full min-h-[34px] items-center justify-between rounded-lg px-2.5 py-1.5 text-left text-[13px] transition-colors ${
                  active
                    ? "bg-accent text-accent-ink font-medium"
                    : "text-muted hover:bg-rail-hover hover:text-ink"
                }`}
              >
                <span className="flex items-center gap-2 truncate">
                  <Icon className="h-4 w-4 shrink-0" />
                  <span className="truncate">{item.label}</span>
                </span>
                <span
                  className={`numeral text-[11px] shrink-0 ${
                    active ? "opacity-80" : "text-faint"
                  }`}
                >
                  {item.meta}
                </span>
              </button>
            );
          })}
        </nav>

        <div className="mt-5 rounded-lg border border-line bg-surface p-3">
          <p className="type-kpi-label text-ink">2-Minute Judge Brief</p>
          <p className="type-meta mt-1 text-faint">
            Inspect verified ContextCon deliverables in under 120 seconds.
          </p>
          <button
            type="button"
            onClick={() => {
              dialogRef.current?.close();
              onOpenJudgeBrief();
            }}
            className="mt-2.5 inline-flex w-full items-center justify-center gap-1.5 rounded-md border border-line-strong bg-subtle px-2.5 py-1.5 text-xs font-medium text-ink hover:bg-rail-hover"
          >
            <Activity className="h-3.5 w-3.5" />
            Open Judge Brief
          </button>
        </div>
      </div>

      <div className="shrink-0 border-t border-line px-3 py-3">
        <div className="flex items-center justify-between gap-2 px-1">
          <div className="min-w-0">
            <p className="font-code truncate text-xs font-medium text-ink">{datapackName}</p>
            <p className="type-meta truncate text-faint">DeepSeek V4.1 Flash</p>
          </div>
          <button
            type="button"
            aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            onClick={() => applyThemeWithoutFreeze(theme === "dark" ? "light" : "dark")}
            className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-line-strong bg-surface text-ink hover:bg-rail-hover"
          >
            {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>
        </div>
        <a
          href="https://github.com/princejain756/contextcon-adlc"
          target="_blank"
          rel="noreferrer"
          className="type-meta mt-2 flex items-center justify-between rounded-md px-1.5 py-1 text-muted hover:bg-rail-hover hover:text-ink"
        >
          <span>GitHub Repository</span>
          <ExternalLink className="h-3.5 w-3.5" />
        </a>
      </div>
    </div>
  );

  return (
    <div className="flex min-h-screen flex-col lg:flex-row">
      <aside className="hidden lg:sticky lg:top-0 lg:flex lg:h-screen lg:w-64 lg:shrink-0 lg:flex-col lg:border-r lg:border-line lg:bg-rail">
        {renderRailContent()}
      </aside>

      <header className="sticky top-0 z-20 flex items-center justify-between border-b border-line bg-rail px-4 py-2.5 lg:hidden">
        <div className="flex items-center gap-2.5">
          <button
            type="button"
            aria-label="Open navigation menu"
            onClick={() => onSetMobileOpen(true)}
            className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-line-strong bg-surface text-ink"
          >
            <Menu className="h-4 w-4" />
          </button>
          <div>
            <p className="font-code text-xs font-semibold text-ink">contextcon-adlc</p>
            <p className="type-meta text-faint">Meko ADLC Audit Portal</p>
          </div>
        </div>
        <button
          type="button"
          aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          onClick={() => applyThemeWithoutFreeze(theme === "dark" ? "light" : "dark")}
          className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-line-strong bg-surface text-ink"
        >
          {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </button>
      </header>

      <dialog
        ref={dialogRef}
        onClose={() => onSetMobileOpen(false)}
        className="m-0 h-full max-h-none w-72 max-w-[85vw] border-r border-line bg-rail p-0 text-ink backdrop:bg-black/45 lg:hidden"
      >
        <div className="flex h-full flex-col">
          <div className="flex items-center justify-between border-b border-line px-4 py-3">
            <span className="font-code text-xs font-semibold text-ink">Navigation</span>
            <button
              type="button"
              aria-label="Close navigation menu"
              onClick={() => dialogRef.current?.close()}
              className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-line bg-surface text-ink"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
          <div className="min-h-0 flex-1">{renderRailContent()}</div>
        </div>
      </dialog>

      <main className="min-w-0 flex-1 px-4 py-5 sm:px-6 sm:py-6 lg:px-8">
        <div className="mx-auto max-w-6xl">{children}</div>
      </main>
    </div>
  );
}
