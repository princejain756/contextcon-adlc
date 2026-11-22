"use client";

import { CheckCircle2, Database, Sparkles } from "lucide-react";
import { formatCount, labelFor, STATUS_LABELS } from "@/lib/display-labels";
import type { PortalSnapshot } from "@/lib/portal-data";

interface AmpSelfLearnViewProps {
  amp: PortalSnapshot["amp_report"];
  selflearn: PortalSnapshot["selflearning_report"];
  telemetry: PortalSnapshot["exported_traces"]["selflearning_status"];
}

export function AmpSelfLearnView({ amp, selflearn, telemetry }: AmpSelfLearnViewProps) {
  const verify = selflearn.selflearning_verify;
  const beforePct = Math.round(verify.before.best_score * 100);
  const afterPct = Math.round(verify.after.best_score * 100);

  return (
    <div className="space-y-5">
      <div>
        <h1 className="type-page text-ink">AMP Postgres 18 Branching & Self-Learning</h1>
        <p className="type-body mt-1 text-muted">
          Copy-on-write database migration verification on AMP Postgres 18 paired with automated search shortfall remediation.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <section className="app-card p-4 sm:p-5">
          <div className="flex items-center justify-between gap-2 border-b border-line pb-3">
            <div className="flex items-center gap-2">
              <Database className="h-4 w-4 text-muted" />
              <h2 className="type-section text-ink">AMP Zero-Copy Postgres 18 Fork</h2>
            </div>
            <span className="pill-success type-pill rounded-full px-2.5 py-0.5">
              {labelFor(STATUS_LABELS, amp.status, "Verified")}
            </span>
          </div>

          <dl className="mt-4 space-y-2.5 text-xs">
            <div className="flex justify-between gap-3">
              <dt className="text-faint">Cluster ID</dt>
              <dd className="font-code text-ink">{amp.cluster_id}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-faint">Postgres Engine</dt>
              <dd className="text-ink">{amp.pg_version.split(" on ")[0].replace(/\s*\(\)\s*$/, "")}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-faint">Main Endpoint & WAL LSN</dt>
              <dd className="font-code text-ink">
                {amp.main_endpoint} ({amp.main_wal_lsn})
              </dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-faint">Zero-Copy Fork Branch</dt>
              <dd className="font-code text-ink">{amp.fork_branch.name}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-faint">Fork Endpoint</dt>
              <dd className="font-code text-ink">{amp.fork_endpoint}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-faint">CoW Inherited Seed Rows</dt>
              <dd className="numeral font-medium text-ink">
                {amp.cow_inherited_account_rows} ledger account row
              </dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-faint">Negative Amount CHECK Enforced</dt>
              <dd className="inline-flex items-center gap-1 font-medium text-ink">
                <CheckCircle2 className="h-3.5 w-3.5 text-green-600 dark:text-green-400" />
                {amp.negative_amount_check_violation_enforced ? "Enforced on Fork" : "Not Enforced"}
              </dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-faint">Compute Budget After Cleanup</dt>
              <dd className="numeral text-ink">
                {amp.amp_core_budget_after.used_cores} / {amp.amp_core_budget_after.max_cores} vCPU ({amp.amp_core_budget_after.tier})
              </dd>
            </div>
          </dl>

          <div className="mt-4 space-y-2 border-t border-line pt-3">
            <div>
              <p className="type-kpi-label text-faint">Verified Tables on Fork</p>
              <div className="mt-1.5 flex flex-wrap gap-1.5">
                {amp.verified_tables.map((tb) => (
                  <span key={tb} className="pill-neutral font-code type-pill rounded-md px-2 py-0.5">
                    {tb}
                  </span>
                ))}
              </div>
            </div>
            <div>
              <p className="type-kpi-label text-faint">Verified Indexes on Fork</p>
              <div className="mt-1.5 flex flex-wrap gap-1.5">
                {amp.verified_indexes.map((ix) => (
                  <span key={ix} className="pill-neutral font-code type-pill rounded-md px-2 py-0.5">
                    {ix}
                  </span>
                ))}
              </div>
            </div>
            <p className="type-meta pt-1 text-faint">
              Report Artifact: <span className="font-code text-ink">{amp.artifact.filename}</span> ({formatCount(amp.artifact.size_bytes)} B)
            </p>
          </div>
        </section>

        <section className="app-card p-4 sm:p-5">
          <div className="flex items-center justify-between gap-2 border-b border-line pb-3">
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-muted" />
              <h2 className="type-section text-ink">Closed-Loop Self-Learning</h2>
            </div>
            <span className="pill-success type-pill rounded-full px-2.5 py-0.5">
              {labelFor(STATUS_LABELS, verify.outcome, "Improved")}
            </span>
          </div>

          <div className="mt-4 rounded-lg border border-line bg-subtle p-3">
            <p className="type-kpi-label text-faint">Uncovered Query Remediated</p>
            <p className="type-body mt-1 font-medium text-ink">
              &ldquo;{selflearn.weak_query}&rdquo;
            </p>
            <p className="type-meta font-code mt-1 text-faint">Log ID: {selflearn.log_id}</p>
          </div>

          <div className="mt-4 space-y-3">
            <div>
              <div className="flex justify-between text-xs">
                <span className="text-muted">
                  Before ADR-007 ({labelFor(STATUS_LABELS, verify.before.band, "Low")} band)
                </span>
                <span className="numeral font-medium text-ink">{verify.before.best_score.toFixed(4)}</span>
              </div>
              <div className="mt-1.5 h-2 w-full overflow-hidden rounded-full bg-subtle">
                <div
                  className="h-full rounded-full"
                  style={{ width: `${beforePct}%`, backgroundColor: "var(--bar-baseline)" }}
                />
              </div>
            </div>

            <div>
              <div className="flex justify-between text-xs">
                <span className="font-medium text-ink">
                  After ADR-007 + Memory ({labelFor(STATUS_LABELS, verify.after.band, "High")} band)
                </span>
                <span className="numeral font-semibold text-ink">{verify.after.best_score.toFixed(4)}</span>
              </div>
              <div className="mt-1.5 h-2 w-full overflow-hidden rounded-full bg-subtle">
                <div
                  className="h-full rounded-full"
                  style={{ width: `${afterPct}%`, backgroundColor: "var(--bar-meko)" }}
                />
              </div>
            </div>
          </div>

          <div className="mt-4 space-y-2.5">
            <div className="rounded-lg border border-line bg-subtle p-3">
              <p className="type-kpi-label text-faint">Scope A: 7-Day Exported Datapack Aggregate (All Searches)</p>
              <div className="mt-2 grid grid-cols-3 gap-2 text-center">
                <div>
                  <p className="type-kpi-label text-faint">Searches</p>
                  <p className="type-section numeral text-ink">{telemetry.breakdown.totals.searches}</p>
                </div>
                <div>
                  <p className="type-kpi-label text-faint">Zero Hits</p>
                  <p className="type-section numeral text-ink">{telemetry.breakdown.totals.zero_results}</p>
                </div>
                <div>
                  <p className="type-kpi-label text-faint">Avg Score</p>
                  <p className="type-section numeral text-ink">{telemetry.breakdown.totals.avg_score.toFixed(4)}</p>
                </div>
              </div>
            </div>
            {selflearn.status_after?.breakdown?.totals && (
              <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-line px-3 py-2 text-xs text-muted">
                <span>Scope B: Immediate <span className="font-code text-ink">status_after</span> window ({selflearn.status_after.breakdown.totals.searches} searches)</span>
                <span className="numeral font-medium text-ink">avg {selflearn.status_after.breakdown.totals.avg_score.toFixed(4)} | high {selflearn.status_after.quality.high}</span>
              </div>
            )}
          </div>

          <div className="mt-4">
            <p className="type-kpi-label text-faint">Top Replayed Verification Hits</p>
            <div className="mt-2 space-y-2">
              {verify.top_results.slice(0, 3).map((hit) => (
                <div key={hit.id} className="rounded-lg border border-line bg-subtle px-3 py-2">
                  <div className="flex items-center justify-between gap-2 text-xs">
                    <span className="pill-neutral type-pill rounded px-1.5 py-0.5 capitalize">{hit.kind}</span>
                    <span className="numeral font-medium text-ink">{hit.score.toFixed(4)}</span>
                  </div>
                  <p className="type-meta mt-1 line-clamp-2 text-muted">{hit.title}</p>
                </div>
              ))}
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
