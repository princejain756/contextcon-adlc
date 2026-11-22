export function labelFor(
  labels: Readonly<Record<string, string>>,
  value: string | null | undefined,
  fallback: string
): string {
  const key = typeof value === "string" ? value.trim().toLowerCase() : "";
  if (!key) return fallback;
  return Object.hasOwn(labels, key) ? labels[key] : fallback;
}

export function formatCount(value: number | string | null | undefined): string {
  const n = typeof value === "string" ? Number(value) : Number(value ?? 0);
  const safe = Number.isFinite(n) ? Math.trunc(n) : 0;
  return new Intl.NumberFormat("en-US").format(safe);
}

export function formatUSD(value: number | string | null | undefined, digits = 6): string {
  const n = typeof value === "string" ? Number(value) : Number(value ?? 0);
  const safe = Number.isFinite(n) ? n : 0;
  return `$${safe.toFixed(digits)}`;
}

export function formatPct(value: number | string | null | undefined, digits = 2): string {
  const n = typeof value === "string" ? Number(value) : Number(value ?? 0);
  const safe = Number.isFinite(n) ? n : 0;
  return `${safe.toFixed(digits)}%`;
}

export function formatSeconds(value: number | string | null | undefined, digits = 2): string {
  const n = typeof value === "string" ? Number(value) : Number(value ?? 0);
  const safe = Number.isFinite(n) ? n : 0;
  return `${safe.toFixed(digits)}s`;
}

export function countLabel(count: number, singular: string, plural = `${singular}s`): string {
  return `${formatCount(count)} ${count === 1 ? singular : plural}`;
}

export const AGENT_LABELS: Readonly<Record<string, string>> = {
  "claude-code-architect": "Claude Code Architect",
  "codex-verifier": "Codex Verifier",
  "pr-review-drift-guard": "PR-Review Drift Guard",
  "amp-verifier": "AMP Branch Verifier",
  "selflearning-auditor": "Self-Learning Auditor",
  "benchmark-runner": "Benchmark Runner",
  "contextcon-seeder": "KB Seeder",
  "portal-exporter": "Portal Exporter",
};

export const STATUS_LABELS: Readonly<Record<string, string>> = {
  changes_requested: "Changes Requested",
  approved: "Approved",
  amp_branch_verified: "Branch Verified",
  completed: "Indexed",
  improved: "Improved",
  low: "Low",
  mid: "Medium",
  medium: "Medium",
  high: "High",
  critical: "Critical",
  cross_agent: "Cross-Agent Direct",
  creator_scoped: "Creator Scoped",
  historical_captured_session: "Historical Trace",
  linked_agent1_report: "Linked Report",
  meko_conversation_get: "Trace Verified",
  external_unverified: "External Unverified",
};

export function severityPillClass(severity: string): string {
  const key = severity.trim().toLowerCase();
  if (key === "critical" || key === "high") return "pill-danger";
  if (key === "medium") return "pill-warning";
  return "pill-neutral";
}

export function formatShortTimestamp(iso: string | null | undefined): string {
  if (!iso) return "Timestamp unavailable";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "UTC",
  }) + " UTC";
}

const themeListeners = new Set<() => void>();

export function subscribeTheme(listener: () => void): () => void {
  themeListeners.add(listener);
  return () => {
    themeListeners.delete(listener);
  };
}

export function getClientThemeSnapshot(): "light" | "dark" {
  if (typeof document === "undefined") return "light";
  return document.documentElement.classList.contains("dark") ? "dark" : "light";
}

export function getServerThemeSnapshot(): "light" | "dark" {
  return "light";
}

export function applyThemeWithoutFreeze(next: "light" | "dark"): void {
  const root = document.documentElement;
  root.classList.add("theme-switching");
  root.classList.toggle("dark", next === "dark");
  void root.offsetHeight;
  try {
    localStorage.setItem("contextcon-theme", next);
  } catch {
    // Ignore storage quota / private mode restrictions
  }
  themeListeners.forEach((fn) => fn());
  let cleaned = false;
  const clearSwitch = () => {
    if (cleaned) return;
    cleaned = true;
    root.classList.remove("theme-switching");
  };
  setTimeout(clearSwitch, 80);
  requestAnimationFrame(() => {
    requestAnimationFrame(clearSwitch);
  });
}
