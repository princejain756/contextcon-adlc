"use client";

import { useState } from "react";
import { ArrowRight, Check, CheckCircle2, Copy, FileCode2, ShieldAlert } from "lucide-react";
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

function CopyIdButton({ value, label }: { value: string; label: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1400);
    } catch {
      // Ignore clipboard failures in restricted environments
    }
  };
  return (
    <button
      type="button"
      aria-label={`Copy ${label}`}
      onClick={handleCopy}
      className="inline-flex items-center gap-1 rounded border border-line px-1.5 py-0.5 text-[10px] font-medium text-muted hover:bg-subtle hover:text-ink"
    >
      {copied ? <Check className="h-3 w-3 text-green-600 dark:text-green-400" /> : <Copy className="h-3 w-3" />}
      {copied ? "Copied" : "Copy"}
    </button>
  );
}

export function HandoffView({ handoff }: HandoffViewProps) {
  const parsedReview = parseAgent3Review(handoff.agent3_review.raw, handoff.agent3_review.findings);
  const a1 = handoff.agent1_claude;
  const a1VerifierBadge =
    a1.verifier === null
      ? { cls: "pill-warning", text: "External Unverified" }
      : a1.verifier.passed
        ? { cls: "pill-success", text: "SQL Verified" }
        : { cls: "pill-danger", text: "Check Failed" };

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="type-page text-ink">Cross-Machine 3-Agent Handoff</h1>
          <p className="type-body mt-1 text-muted">
            Three distinct models linked via Meko <span className="font-code text-ink">run_id</span> across Apple Silicon Mac mini and MacBook Pro with zero copy-paste prompts.
          </p>
        </div>
        <div className="flex items-center gap-2 self-start sm:self-auto">
          <span className="pill-neutral type-pill font-code rounded-full px-3 py-1">
            Run ID: {handoff.run_id}
          </span>
          <CopyIdButton value={handoff.run_id} label="run_id" />
        </div>
      </div>

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="app-card p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="pill-neutral type-pill rounded-full px-2 py-0.5">Stage 1 | Mac mini</span>
            <div className="flex items-center gap-1.5">
              {a1.provenance && (
                <span className="pill-neutral type-pill rounded-full px-2 py-0.5">
                  {labelFor(STATUS_LABELS, a1.provenance, a1.provenance)}
                </span>
              )}
              <span className={`${a1VerifierBadge.cls} type-pill rounded-full px-2 py-0.5`}>
                {a1VerifierBadge.text}
              </span>
            </div>
          </div>
          <h2 className="type-section mt-2.5 text-ink">
            {labelFor(AGENT_LABELS, a1.agent_id, "Agent 1")}
          </h2>
          <p className="type-body mt-1 text-muted">
            Drafted two-phase refund ledger migration <span className="font-code text-ink">0003_add_refund_ledger.sql</span>, stored promoted schema gotcha memory, and attached SQL artifact.
          </p>
          <dl className="mt-3 space-y-1.5 border-t border-line pt-3 text-xs">
            <div className="flex items-center justify-between gap-2">
              <dt className="text-faint">Conversation</dt>
              <dd className="flex items-center gap-1.5 font-code text-ink">
                <span>{a1.conversation_id.slice(0, 12)}...</span>
                <CopyIdButton value={a1.conversation_id} label="Agent 1 conversation ID" />
              </dd>
            </div>
            <div className="flex items-center justify-between gap-2">
              <dt className="text-faint">Promoted Memory</dt>
              <dd className="flex items-center gap-1.5 font-code text-ink">
                <span>{a1.memory_ids[0] ? `${a1.memory_ids[0].slice(0, 12)}...` : "None recorded"}</span>
                {a1.memory_ids[0] && <CopyIdButton value={a1.memory_ids[0]} label="memory ID" />}
              </dd>
            </div>
            <div className="flex items-center justify-between gap-2">
              <dt className="text-faint">Artifact SHA-256</dt>
              <dd className="flex items-center gap-1.5 font-code text-ink">
                <span>{a1.artifact_hash.slice(0, 12)}...</span>
                <CopyIdButton value={a1.artifact_hash} label="artifact SHA-256" />
              </dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt className="text-faint">Tokens (In / Out)</dt>
              <dd className="numeral text-ink">
                {a1.tokens ? `${formatCount(a1.tokens.input)} / ${formatCount(a1.tokens.output)}` : "Unavailable"}
              </dd>
            </div>
          </dl>
        </div>

        <div className="app-card p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
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
            <div className="flex items-center justify-between gap-2">
              <dt className="text-faint">Conversation</dt>
              <dd className="flex items-center gap-1.5 font-code text-ink">
                <span>{handoff.agent2_codex.conversation_id.slice(0, 12)}...</span>
                <CopyIdButton value={handoff.agent2_codex.conversation_id} label="Agent 2 conversation ID" />
              </dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt className="text-faint">SQL Rule Check</dt>
              <dd className="inline-flex items-center gap-1 font-medium text-ink">
                <CheckCircle2 className="h-3.5 w-3.5 text-green-600 dark:text-green-400" />
                {handoff.agent2_codex.sql_check.passed ? "Passed" : "Violations"}
              </dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt className="text-faint">Trace SHA-256 Match</dt>
              <dd className="numeral text-ink">
                {handoff.agent2_codex.artifact_sha256_matches_agent1_trace_output || handoff.agent2_codex.artifact_sha256_verified
                  ? "Verified"
                  : "Not recorded"}
              </dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt className="text-faint">Elapsed / Tokens</dt>
              <dd className="numeral text-ink">
                {formatSeconds(handoff.agent2_codex.elapsed_s)} ({formatCount(handoff.agent2_codex.tokens.in)} / {formatCount(handoff.agent2_codex.tokens.out)})
              </dd>
            </div>
          </dl>
        </div>

        <div className="app-card p-4">
          <div className="flex items-center justify-between gap-2">
            <span className="pill-neutral type-pill rounded-full px-2 py-0.5">Stage 3 | Drift Guard</span>
            <span className="pill-danger type-pill rounded-full px-2 py-0.5">
              {labelFor(STATUS_LABELS, parsedReview.decision, "Changes Requested")}
            </span>
          </div>
          <h2 className="type-section mt-2.5 text-ink">
            {labelFor(AGENT_LABELS, handoff.agent3_review.agent_id, "Agent 3")}
          </h2>
          <p className="type-body mt-1 text-muted">
            Audited a drifted PR diff against shared ADR chunks and Stage 1 promoted gotcha memory, flagging {handoff.agent3_review.findings.length} static + 2 grounded ADR violations.
          </p>
          <dl className="mt-3 space-y-1.5 border-t border-line pt-3 text-xs">
            <div className="flex items-center justify-between gap-2">
              <dt className="text-faint">Conversation</dt>
              <dd className="flex items-center gap-1.5 font-code text-ink">
                <span>{handoff.agent3_review.conversation_id.slice(0, 12)}...</span>
                <CopyIdButton value={handoff.agent3_review.conversation_id} label="Agent 3 conversation ID" />
              </dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt className="text-faint">Audit Artifact</dt>
              <dd className="font-code text-ink">{handoff.agent3_review.audit_artifact.filename}</dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt className="text-faint">Artifact Size</dt>
              <dd className="numeral text-ink">{formatCount(handoff.agent3_review.audit_artifact.size_bytes)} B</dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt className="text-faint">Elapsed / Tokens</dt>
              <dd className="numeral text-ink">
                {formatSeconds(handoff.agent3_review.elapsed_s)} ({formatCount(handoff.agent3_review.tokens.in)} / {formatCount(handoff.agent3_review.tokens.out)})
              </dd>
            </div>
          </dl>
        </div>
      </section>

      {a1.provenance_note && (
        <p className="type-meta rounded-lg border border-line bg-subtle px-3.5 py-2.5 text-muted">
          <strong className="text-ink">Provenance note:</strong> {a1.provenance_note}
        </p>
      )}

      <section className="app-card p-4 sm:p-5">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line pb-3">
          <div className="flex items-center gap-2">
            <ShieldAlert className="h-4 w-4 text-red-600 dark:text-red-400" />
            <h2 className="type-section text-ink">2-Minute Executive Decision Summary</h2>
          </div>
          <span className="pill-danger type-pill rounded-full px-2.5 py-0.5">
            {labelFor(STATUS_LABELS, parsedReview.decision, "Changes Requested")}
          </span>
        </div>
        <p className="type-body mt-3 leading-relaxed text-ink">{parsedReview.explainUnder2Min}</p>

        <div className="mt-4 grid grid-cols-1 gap-2.5 md:grid-cols-2">
          {parsedReview.findings.map((f, idx) => (
            <div key={idx} className="rounded-lg border border-line bg-subtle p-3">
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
