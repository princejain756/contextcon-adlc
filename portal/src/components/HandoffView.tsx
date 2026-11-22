"use client";

import { ArrowRight, CheckCircle2, FileCode2, ShieldAlert } from "lucide-react";
import {
  AGENT_LABELS,
  formatCount,
  formatSeconds,
  labelFor,
  severityPillClass,
  STATUS_LABELS,
} from "@/lib/display-labels";
import { parseAgent3Review, PortalSnapshot } from "@/lib/portal-data";

interface HandoffViewProps {
  handoff: PortalSnapshot["handoff_report"];
}

export function HandoffView({ handoff }: HandoffViewProps) {
  const parsedReview = parseAgent3Review(handoff.agent3_review.raw, handoff.agent3_review.findings);

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="type-page text-ink">Cross-Machine 3-Agent Handoff</h1>
          <p className="type-body mt-1 text-muted">
            Three distinct models linked via Meko <span className="font-code text-ink">run_id</span> across Apple Silicon Mac mini and MacBook Pro with zero copy-paste prompts.
          </p>
        </div>
        <span className="pill-neutral type-pill font-code self-start rounded-full px-3 py-1 sm:self-auto">
          Run ID: {handoff.run_id}
        </span>
      </div>

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="app-card p-4">
          <div className="flex items-center justify-between gap-2">
            <span className="pill-neutral type-pill rounded-full px-2 py-0.5">Stage 1 | Mac mini</span>
            <span className="pill-success type-pill rounded-full px-2 py-0.5">SQL Verified</span>
          </div>
          <h2 className="type-section mt-2.5 text-ink">
            {labelFor(AGENT_LABELS, handoff.agent1_claude.agent_id, "Agent 1")}
          </h2>
          <p className="type-body mt-1 text-muted">
            Drafted two-phase refund ledger migration <span className="font-code text-ink">0003_add_refund_ledger.sql</span>, stored promoted schema gotcha memory, and attached SQL artifact.
          </p>
          <dl className="mt-3 space-y-1.5 border-t border-line pt-3 text-xs">
            <div className="flex justify-between gap-2">
              <dt className="text-faint">Conversation</dt>
              <dd className="font-code text-ink">{handoff.agent1_claude.conversation_id.slice(0, 14)}...</dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt className="text-faint">Promoted Memory</dt>
              <dd className="font-code text-ink">{handoff.agent1_claude.memory_ids[0]?.slice(0, 14)}...</dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt className="text-faint">Artifact SHA-256</dt>
              <dd className="font-code text-ink">{handoff.agent1_claude.artifact_hash.slice(0, 14)}...</dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt className="text-faint">Tokens (In / Out)</dt>
              <dd className="numeral text-ink">
                {formatCount(handoff.agent1_claude.tokens.input)} / {formatCount(handoff.agent1_claude.tokens.output)}
              </dd>
            </div>
          </dl>
        </div>

        <div className="app-card p-4">
          <div className="flex items-center justify-between gap-2">
            <span className="pill-neutral type-pill rounded-full px-2 py-0.5">Stage 2 | MacBook Pro</span>
            <span className="pill-success type-pill rounded-full px-2 py-0.5">
              {labelFor(STATUS_LABELS, handoff.agent2_codex.artifact_access_mode, "Cross-Agent")}
            </span>
          </div>
          <h2 className="type-section mt-2.5 text-ink">
            {labelFor(AGENT_LABELS, handoff.agent2_codex.agent_id, "Agent 2")}
          </h2>
          <p className="type-body mt-1 text-muted">
            Resumed from Meko artifact and promoted memories alone inside read-only Codex CLI, validated SQL rules ({handoff.agent2_codex.sql_check.details.sql_len} bytes), and emitted guard code.
          </p>
          <dl className="mt-3 space-y-1.5 border-t border-line pt-3 text-xs">
            <div className="flex justify-between gap-2">
              <dt className="text-faint">Conversation</dt>
              <dd className="font-code text-ink">{handoff.agent2_codex.conversation_id.slice(0, 14)}...</dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt className="text-faint">SQL Constraint Check</dt>
              <dd className="inline-flex items-center gap-1 text-ink">
                <CheckCircle2 className="h-3.5 w-3.5 text-green-600 dark:text-green-400" />
                Passed ({handoff.agent2_codex.sql_check.rule_violations.length} violations)
              </dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt className="text-faint">Latency</dt>
              <dd className="numeral text-ink">{formatSeconds(handoff.agent2_codex.elapsed_s)}</dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt className="text-faint">Tokens (In / Out)</dt>
              <dd className="numeral text-ink">
                {formatCount(handoff.agent2_codex.tokens.in)} / {formatCount(handoff.agent2_codex.tokens.out)}
              </dd>
            </div>
          </dl>
        </div>

        <div className="app-card p-4">
          <div className="flex items-center justify-between gap-2">
            <span className="pill-neutral type-pill rounded-full px-2 py-0.5">Stage 3 | Drift Gate</span>
            <span className="pill-danger type-pill rounded-full px-2 py-0.5">
              {labelFor(STATUS_LABELS, parsedReview.decision, "Blocked")}
            </span>
          </div>
          <h2 className="type-section mt-2.5 text-ink">
            {labelFor(AGENT_LABELS, handoff.agent3_review.agent_id, "Agent 3")}
          </h2>
          <p className="type-body mt-1 text-muted">
            Reviewed drifted PR diff against ADR KB documents and promoted memory, caught {handoff.agent3_review.findings.length} static plus 2 additional ADR issues, and persisted JSON report.
          </p>
          <dl className="mt-3 space-y-1.5 border-t border-line pt-3 text-xs">
            <div className="flex justify-between gap-2">
              <dt className="text-faint">Conversation</dt>
              <dd className="font-code text-ink">{handoff.agent3_review.conversation_id.slice(0, 14)}...</dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt className="text-faint">Audit Artifact</dt>
              <dd className="font-code text-right text-ink">
                {handoff.agent3_review.audit_artifact.filename}
                <span className="ml-1 text-faint">({formatCount(handoff.agent3_review.audit_artifact.size_bytes)}&nbsp;B)</span>
              </dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt className="text-faint">Latency</dt>
              <dd className="numeral text-ink">{formatSeconds(handoff.agent3_review.elapsed_s)}</dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt className="text-faint">Tokens (In / Out)</dt>
              <dd className="numeral text-ink">
                {formatCount(handoff.agent3_review.tokens.in)} / {formatCount(handoff.agent3_review.tokens.out)}
              </dd>
            </div>
          </dl>
        </div>
      </section>

      <section className="app-card p-4 sm:p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <ShieldAlert className="h-4 w-4 text-red-600 dark:text-red-400" />
            <h2 className="type-section text-ink">2-Minute Plain-Language Decision Summary</h2>
          </div>
          <span className="pill-danger type-pill rounded-full px-2.5 py-0.5">
            Decision: {labelFor(STATUS_LABELS, parsedReview.decision, "Changes Requested")}
          </span>
        </div>
        <p className="type-body mt-3 rounded-lg border border-line bg-subtle p-3.5 leading-relaxed text-ink">
          {parsedReview.explainUnder2Min}
        </p>

        <h3 className="type-kpi-label mt-5 text-faint">
          Grounded ADR Findings Flagged in Diff ({parsedReview.findings.length})
        </h3>
        <div className="mt-2.5 space-y-2.5">
          {parsedReview.findings.map((f, idx) => (
            <div key={`${f.adr}-${idx}`} className="rounded-lg border border-line bg-subtle p-3">
              <div className="flex items-center justify-between gap-2">
                <span className="font-code text-xs font-semibold text-ink">{f.adr}</span>
                <span className={`type-pill rounded-full px-2 py-0.5 ${severityPillClass(f.severity)}`}>
                  {labelFor(STATUS_LABELS, f.severity, "Review")}
                </span>
              </div>
              <p className="type-body mt-1.5 text-muted">{f.explanation || f.finding}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="app-card p-4 sm:p-5">
        <div className="flex items-center gap-2">
          <FileCode2 className="h-4 w-4 text-muted" />
          <h2 className="type-section text-ink">Agent 2 Generated SQL Lock-Safety Guard Preview</h2>
        </div>
        <p className="type-meta mt-1 text-faint">
          Synthesized independently by Codex Verifier from Meko artifacts and memories without access to Claude Code local files <ArrowRight className="inline h-3 w-3" />
        </p>
        <pre className="font-code mt-3 max-h-72 overflow-auto rounded-lg border border-line bg-subtle p-3.5 text-[11px] leading-relaxed text-ink">
          {handoff.agent2_codex.code_preview}
        </pre>
      </section>
    </div>
  );
}
