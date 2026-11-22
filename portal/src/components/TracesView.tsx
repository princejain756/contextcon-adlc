"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, FileText, Search } from "lucide-react";
import {
  AGENT_LABELS,
  formatCount,
  formatShortTimestamp,
  labelFor,
  STATUS_LABELS,
} from "@/lib/display-labels";
import type { PortalSnapshot } from "@/lib/portal-data";

interface TracesViewProps {
  data: PortalSnapshot;
}

type ExplorerSubTab = "conversations" | "memories" | "kb";

export function TracesView({ data }: TracesViewProps) {
  const [subTab, setSubTab] = useState<ExplorerSubTab>("conversations");
  const [query, setQuery] = useState("");
  const [agentFilter, setAgentFilter] = useState<string>("all");
  const [expandedId, setExpandedId] = useState<string>(
    data.exported_traces.conversations[0]?.id ?? ""
  );

  const conversations = data.exported_traces.conversations;
  const memories = data.exported_traces.memories.memories;
  const kbFiles = data.seed_report.uploaded;

  const uniqueAgents = Array.from(new Set(conversations.map((c) => c.agent_id))).sort();
  const q = query.trim().toLowerCase();

  const filteredConversations = conversations.filter((c) => {
    if (agentFilter !== "all" && c.agent_id !== agentFilter) return false;
    if (!q) return true;
    return (
      c.title.toLowerCase().includes(q) ||
      c.id.toLowerCase().includes(q) ||
      c.agent_id.toLowerCase().includes(q) ||
      c.messages.some(
        (m) =>
          (m.input || "").toLowerCase().includes(q) ||
          (m.reasoning || "").toLowerCase().includes(q)
      )
    );
  });

  const filteredMemories = memories.filter((m) => {
    if (!q) return true;
    return (
      m.data.toLowerCase().includes(q) ||
      m.agent_id.toLowerCase().includes(q) ||
      labelFor(AGENT_LABELS, m.agent_id, m.agent_id).toLowerCase().includes(q)
    );
  });

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="type-page text-ink">Trace, Memory & KB Explorer</h1>
          <p className="type-body mt-1 text-muted">
            Full audit export across {data.traces_fetched_ok ?? conversations.length}/{data.traces_attempted ?? conversations.length} conversations ({data.fetch_errors_count ?? 0} fetch errors), {data.exported_traces.memories.total} stored memories, and {kbFiles.length} plain-text KB files ({formatShortTimestamp(data.exported_at)}).
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {[
            { id: "conversations" as const, label: `Traces (${conversations.length})` },
            { id: "memories" as const, label: `Memories (${memories.length})` },
            { id: "kb" as const, label: `KB Files (${kbFiles.length})` },
          ].map((btn) => (
            <button
              key={btn.id}
              type="button"
              onClick={() => setSubTab(btn.id)}
              className={`type-pill rounded-full px-3 py-1 transition-colors ${
                subTab === btn.id
                  ? "bg-accent text-accent-ink"
                  : "pill-neutral hover:bg-rail-hover"
              }`}
            >
              {btn.label}
            </button>
          ))}
        </div>
      </div>

      {subTab !== "kb" && (
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-faint" />
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={
                subTab === "conversations"
                  ? "Filter traces by title, conversation ID, reasoning, or prompt..."
                  : "Filter collective and session memories..."
              }
              className="app-field type-body w-full py-2 pr-3 pl-9"
            />
          </div>
          {subTab === "conversations" && (
            <div className="flex flex-wrap gap-1.5">
              <button
                type="button"
                onClick={() => setAgentFilter("all")}
                className={`type-pill rounded-full px-2.5 py-1 ${
                  agentFilter === "all" ? "bg-accent text-accent-ink" : "pill-neutral"
                }`}
              >
                All Agents
              </button>
              {uniqueAgents.map((aid) => (
                <button
                  key={aid}
                  type="button"
                  onClick={() => setAgentFilter(aid)}
                  className={`type-pill rounded-full px-2.5 py-1 ${
                    agentFilter === aid ? "bg-accent text-accent-ink" : "pill-neutral"
                  }`}
                >
                  {labelFor(AGENT_LABELS, aid, aid)}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {subTab === "conversations" && (
        <div className="space-y-3">
          {filteredConversations.map((conv) => {
            const expanded = expandedId === conv.id;
            return (
              <div key={conv.id} className="app-card overflow-hidden">
                <button
                  type="button"
                  onClick={() => setExpandedId(expanded ? "" : conv.id)}
                  className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left hover:bg-subtle/60"
                >
                  <div className="flex min-w-0 items-center gap-2.5">
                    {expanded ? (
                      <ChevronDown className="h-4 w-4 shrink-0 text-muted" />
                    ) : (
                      <ChevronRight className="h-4 w-4 shrink-0 text-muted" />
                    )}
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-sm font-medium text-ink">{conv.title}</span>
                        <span className="pill-neutral type-pill rounded-full px-2 py-0.5">
                          {labelFor(AGENT_LABELS, conv.agent_id, conv.agent_id)}
                        </span>
                        {conv.run_id && (
                          <span className="pill-success type-pill font-code rounded-full px-2 py-0.5">
                            run {conv.run_id.slice(0, 8)}
                          </span>
                        )}
                      </div>
                      <p className="type-meta font-code mt-0.5 text-faint">
                        {conv.id} | {formatShortTimestamp(conv.created_at)}
                      </p>
                    </div>
                  </div>
                  <span className="pill-neutral type-pill numeral shrink-0 rounded-full px-2.5 py-0.5">
                    {conv.messages.length} {conv.messages.length === 1 ? "turn" : "turns"}
                  </span>
                </button>

                {expanded && (
                  <div className="space-y-3 border-t border-line bg-subtle p-4">
                    {conv.messages.map((m, idx) => (
                      <div key={m.message_id} className="rounded-lg border border-line bg-surface p-3.5">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span className="type-kpi-label text-faint">Turn {idx + 1}</span>
                          <span className="type-meta text-faint">{formatShortTimestamp(m.created_at)}</span>
                        </div>
                        <p className="type-body mt-1.5 font-medium text-ink">{m.input}</p>
                        {m.reasoning && (
                          <div className="mt-2 rounded-md border border-line bg-subtle p-2.5">
                            <p className="type-kpi-label text-faint">Logged Agent Reasoning</p>
                            <p className="type-meta mt-0.5 text-muted">{m.reasoning}</p>
                          </div>
                        )}
                        {Array.isArray(m.plan) && m.plan.length > 0 && (
                          <div className="mt-2">
                            <p className="type-kpi-label text-faint">Logged Plan</p>
                            <ul className="type-meta mt-1 list-disc pl-4 text-muted">
                              {m.plan.map((step, i) => (
                                <li key={i}>{step}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                        <details className="mt-2">
                          <summary className="type-meta cursor-pointer font-medium text-ink">
                            View Output Preview
                          </summary>
                          <pre className="font-code mt-2 max-h-48 overflow-auto rounded-md border border-line bg-subtle p-2.5 text-[11px] text-ink">
                            {(m.output || "").slice(0, 1200)}
                          </pre>
                        </details>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
          {filteredConversations.length === 0 && (
            <div className="app-card p-6 text-center">
              <p className="type-body text-muted">No matching conversation traces found.</p>
            </div>
          )}
        </div>
      )}

      {subTab === "memories" && (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {filteredMemories.map((mem) => (
            <div key={mem.id} className="app-card p-4">
              <div className="flex items-center justify-between gap-2">
                <span className="pill-neutral type-pill rounded-full px-2 py-0.5">
                  {labelFor(AGENT_LABELS, mem.agent_id, mem.agent_id)}
                </span>
                <span className="type-meta text-faint">{formatShortTimestamp(mem.created_at)}</span>
              </div>
              <p className="type-body mt-2 text-ink">{mem.data}</p>
              <p className="type-meta font-code mt-2 text-faint">Memory {mem.id.slice(0, 16)}...</p>
            </div>
          ))}
        </div>
      )}

      {subTab === "kb" && (
        <div className="app-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-left">
              <thead>
                <tr className="border-b border-line bg-subtle text-faint">
                  <th className="type-table-head px-3 py-2.5">Source File</th>
                  <th className="type-table-head px-3 py-2.5">Indexed Plain-Text Key</th>
                  <th className="type-table-head px-3 py-2.5 text-right">Size (B)</th>
                  <th className="type-table-head px-3 py-2.5 text-right">Tokens</th>
                  <th className="type-table-head px-3 py-2.5">Status</th>
                </tr>
              </thead>
              <tbody>
                {kbFiles.map((f) => (
                  <tr key={f.filename} className="border-b border-line">
                    <td className="type-table-cell font-code px-3 py-2 text-ink">
                      <FileText className="mr-1.5 inline h-3.5 w-3.5 text-faint" />
                      {f.source_file}
                    </td>
                    <td className="type-table-cell font-code px-3 py-2 text-muted">{f.filename}</td>
                    <td className="type-table-cell numeral px-3 py-2 text-right text-muted">
                      {formatCount(f.bytes)}
                    </td>
                    <td className="type-table-cell numeral px-3 py-2 text-right text-ink">
                      {formatCount(f.tokens_cl100k)}
                    </td>
                    <td className="type-table-cell px-3 py-2">
                      <span className="pill-success type-pill rounded-full px-2 py-0.5">
                        {f.status?.state
                          ? labelFor(STATUS_LABELS, f.status.state, "Indexed")
                          : "Indexed"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
