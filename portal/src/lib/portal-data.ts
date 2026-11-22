import rawSnapshot from "@/data/portal_snapshot.json";

export interface BenchmarkArm {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  reference_cost_usd: number;
  passed: boolean;
  rule_violations: string[];
  violation_count: number;
  output_preview: string;
  retries?: number;
  latency_s?: number;
  search_latency_s?: number;
  llm_latency_s?: number;
  total_latency_s?: number;
}

export interface BenchmarkTaskRow {
  task_id: string;
  title: string;
  baseline: BenchmarkArm;
  meko: BenchmarkArm;
}

export interface BenchmarkSummary {
  model: string;
  effort: string;
  cwd: string;
  tokenizer: string;
  reference_pricing: string;
  corpus: string;
  search_limit: number;
  baseline_repo_context_tokens: number;
  conversation_id: string;
  task_count: number;
  baseline: {
    total_tokens: number;
    prompt_tokens: number;
    avg_tokens_per_task: number;
    avg_latency_s: number;
    total_latency_s?: number;
    reference_cost_usd: number;
    passed_count: number;
    total_violations: number;
  };
  meko: {
    total_tokens: number;
    prompt_tokens: number;
    avg_tokens_per_task: number;
    avg_latency_s: number;
    completed_attempt_total_latency_s?: number;
    completed_attempt_avg_latency_s?: number;
    reference_cost_usd: number;
    passed_count: number;
    total_violations: number;
  };
  deltas: {
    prompt_token_reduction_pct: number;
    total_token_reduction_pct: number;
    cost_reduction_pct: number;
    latency_change_pct: number;
  };
  retry_inclusive_lower_bound_total_s?: number;
  retry_inclusive_lower_bound_avg_s?: number;
  retry_inclusive_lower_bound_change_pct?: number;
  timing_note?: string;
}

export interface DriftFinding {
  adr: string;
  severity: string;
  finding?: string;
  explanation?: string;
}

export interface ParsedAgent3Review {
  decision: string;
  findings: DriftFinding[];
  explainUnder2Min: string;
}

export interface ConversationMessage {
  message_id: string;
  conversation_id: string;
  input: string;
  output: string;
  reasoning: string | null;
  plan: string[] | string | null;
  metadata: Record<string, unknown> | string | null;
  created_at: string;
}

export interface ExportedConversation {
  id: string;
  agent_id: string;
  run_id: string | null;
  title: string;
  metadata: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
  message_count: number;
  messages: ConversationMessage[];
}

export interface ExportedMemory {
  id: string;
  data: string;
  agent_id: string;
  conversation_id: string | null;
  created_at: string;
}

export interface UploadedKbFile {
  source_file: string;
  filename: string;
  bytes: number;
  tokens_cl100k: number;
  already_uploaded: boolean;
  status: {
    state?: string;
    chunks_processed?: number;
    document_status?: string;
  };
}

export interface PortalSnapshot {
  seed_report: {
    conversation_id: string;
    uploaded: UploadedKbFile[];
    symbols_preserved: Record<string, boolean>;
    adr007_status: { present_before_check: boolean; reseeded: boolean };
    datapack: {
      datapack_id: string;
      datapack_name: string;
      knowledge_chunk_count: number;
      memory_count: number;
      collective_memory_count: number;
    };
  };
  amp_report: {
    conversation_id: string;
    status: string;
    allowed_cidr: string;
    cluster_id: string;
    main_branch_id: string;
    main_endpoint: string;
    main_branch_seeded_accounts: number;
    main_wal_lsn: string;
    fork_branch: { branch_id: string; name: string };
    fork_endpoint: string;
    pg_version: string;
    cow_inherited_account_rows: number;
    verified_tables: string[];
    verified_indexes: string[];
    negative_amount_check_violation_enforced: boolean;
    artifact: { artifact_id: string; content_hash: string; filename: string; size_bytes: number };
    amp_core_budget_before: { tier: string; used_cores: number; max_cores: number };
    amp_core_budget_after: { tier: string; used_cores: number; max_cores: number };
  };
  handoff_report: {
    run_id: string;
    agent1_claude: {
      conversation_id: string;
      agent_id: string;
      provenance?: string;
      provenance_note?: string;
      memory_ids: string[];
      artifact_hash: string;
      verifier: { passed: boolean; rule_violations: string[] } | null;
      tokens: { input: number; output: number } | null;
    };
    agent2_codex: {
      conversation_id: string;
      agent_id: string;
      artifact_access_mode: string;
      artifact_sha256_matches_agent1_trace_output?: boolean;
      artifact_sha256_verified?: boolean;
      sql_check: { passed: boolean; rule_violations: string[]; details: { sql_len: number } };
      elapsed_s: number;
      tokens: { in: number; out: number };
      code_preview: string;
    };
    agent3_review: {
      conversation_id: string;
      agent_id: string;
      findings: DriftFinding[];
      elapsed_s: number;
      tokens: { in: number; out: number };
      audit_artifact: { artifact_id: string; content_hash: string; filename: string; size_bytes: number };
      raw: string;
    };
  };
  selflearning_report: {
    conversation_id: string;
    weak_query: string;
    log_id: string;
    status_after?: {
      quality: { pct: number; potential_pct: number; searches: number; high: number };
      breakdown: {
        totals: { avg_score: number; avg_elapsed_ms: number; searches: number; zero_results: number };
        by_band?: { high: number; mid: number; low: number };
      };
    };
    selflearning_verify: {
      test_prompt_id: string;
      query: string;
      before: { band: string; best_score: number };
      after: { band: string; best_score: number };
      outcome: string;
      hits_above_mid: number;
      hint: string;
      top_results: Array<{
        score: number;
        s: string;
        id: string;
        title: string;
        kind: string;
      }>;
    };
  };
  benchmark_results: {
    summary: BenchmarkSummary;
    tasks: BenchmarkTaskRow[];
  };
  exported_at?: string;
  traces_count: number;
  traces_attempted?: number;
  traces_fetched_ok?: number;
  fetch_errors_count?: number;
  exported_traces: {
    exported_at?: string;
    datapack_name: string;
    datapack_id: string;
    datapack: {
      memory_count: number;
      knowledge_count: number;
      knowledge_chunk_count: number;
      collective_memory_count: number;
    };
    conversations: ExportedConversation[];
    memories: {
      total: number;
      memories: ExportedMemory[];
    };
    selflearning_status: {
      quality: { pct: number; potential_pct: number; searches: number; high: number };
      breakdown: {
        totals: { avg_score: number; avg_elapsed_ms: number; searches: number; zero_results: number };
        by_band: { high: number; mid: number; low: number };
      };
    };
  };
}

export const portalData = rawSnapshot as unknown as PortalSnapshot;

export function parseAgent3Review(raw: string, fallbackFindings: DriftFinding[]): ParsedAgent3Review {
  const fenceMatch = raw.match(/```json\s*\n([\s\S]*?)```/i);
  const candidate = fenceMatch ? fenceMatch[1] : raw;
  try {
    const parsed = JSON.parse(candidate) as {
      decision?: string;
      findings?: DriftFinding[];
      explain_this_decision_under_2min?: string;
    };
    return {
      decision: parsed.decision || "changes_requested",
      findings: Array.isArray(parsed.findings) && parsed.findings.length > 0 ? parsed.findings : fallbackFindings,
      explainUnder2Min:
        parsed.explain_this_decision_under_2min ||
        "The pull request was blocked because its proposed code violates database lock guards, financial precision rules, PII logging standards, and parameterized tenant SQL requirements.",
    };
  } catch {
    return {
      decision: "changes_requested",
      findings: fallbackFindings,
      explainUnder2Min:
        "The pull request was blocked because its proposed code violates database lock guards, financial precision rules, PII logging standards, and parameterized tenant SQL requirements.",
    };
  }
}

export function getBenchmarkCompletionTotals(tasks: BenchmarkTaskRow[]): {
  baselineCompletionTokens: number;
  mekoCompletionTokens: number;
  baselineTotalLatency: number;
  mekoSearchLatency: number;
  mekoLlmLatency: number;
  mekoTotalLatency: number;
} {
  let baselineCompletionTokens = 0;
  let mekoCompletionTokens = 0;
  let baselineTotalLatency = 0;
  let mekoSearchLatency = 0;
  let mekoLlmLatency = 0;
  let mekoTotalLatency = 0;

  for (const t of tasks) {
    baselineCompletionTokens += t.baseline.completion_tokens;
    mekoCompletionTokens += t.meko.completion_tokens;
    baselineTotalLatency += t.baseline.latency_s ?? 0;
    mekoSearchLatency += t.meko.search_latency_s ?? 0;
    mekoLlmLatency += t.meko.llm_latency_s ?? 0;
    mekoTotalLatency += t.meko.total_latency_s ?? 0;
  }

  return {
    baselineCompletionTokens,
    mekoCompletionTokens,
    baselineTotalLatency,
    mekoSearchLatency,
    mekoLlmLatency,
    mekoTotalLatency,
  };
}
