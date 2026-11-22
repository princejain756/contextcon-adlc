# Architecture

`contextcon-adlc` connects local coding-agent CLIs across two Apple Silicon machines (`mac-mini` and `macbookpro`) to one shared Meko Cloud datapack (`56a399c1-e5a5-4027-a5c4-f7d1807c2a41`) and AMP Postgres 18 cluster (`e35a17cf-fa04-4186-a523-24f66c9bb70c`).

## 1. Streamable HTTP MCP Client (`src/meko_adlc/mcp_client.py`)

Instead of relying on an interactive local desktop Keychain daemon (`meko: no such secret` inside non-interactive SSH shells), the orchestrator talks directly to `https://mcp.mekodata.ai/mcp` using Python stdlib `urllib.request`:

- **Session Handshake**: Calls `initialize` once per `MekoMCPClient` instance, stores `Mcp-Session-Id`, and sends `notifications/initialized`.
- **Dual Response Decoding**: `parse_mcp_http_payload` accepts both `application/json` and SSE `text/event-stream` (`data:` JSON-RPC frames) and unwraps nested JSON error payloads into `MekoToolError`.
- **Meko v3.2.4 Protocol Constraints Handled Explicitly**:
  - Injects `conversation_id` when required by tools (`conversation_id_required` enforcement).
  - Preserves creator-matching `agent_id` in `conversation_get` to satisfy `agent_id_mismatch` checks while linking sub-sessions with `run_id`.
  - Serializes `metadata` as JSON strings where MCP schemas expect string metadata, and passes string arrays for `plan`.
  - Encodes `3072`-byte `content_head_base64` previews for `knowledgebase_upload_document` and builds ordered `multipart/form-data` bodies for presigned S3 POST (`fields` before `file`).

## 2. Knowledge Base Indexing & Plain-`.txt` Fidelity Fix

During initial seeding, uploading raw `.md` files caused Meko's markdown parser to strip inline backtick spans (for example `` `ROUND_HALF_EVEN` ``, `` `hmac.compare_digest` ``, and `` `v1=` `` disappeared into blank spaces inside indexed chunks, breaking symbol recall on benchmark `T04`).

`seed_knowledge_base()` (`src/meko_adlc/workflows.py`) resolves this by converting markdown with `_strip_md_for_txt()` (removing markdown backtick punctuation while keeping identifier tokens intact) and indexing the complete symmetric 19-file corpus as `.txt` documents:

- 9 team standards documents (`ADR-001`..`ADR-006`, `INC-2026-041`, `INC-2026-078`, `SERVICE_CONTRACTS_AND_RUNBOOKS.md`) + `MEKO.md`
- 7 Python modules from `target_repo/ledger_service/` prefixed with `FILE: target_repo/ledger_service/<name>` (`code_ledger_service_*.txt`)
- 2 SQL migrations from `target_repo/sql/migrations/` prefixed with `FILE: target_repo/sql/migrations/<name>` (`sql_*.txt`)
- `ADR-007_settlement_cutoff_and_holiday_windows.md` recovered/verified cleanly from the self-learning loop

All `19` corpus entries verified `state == "completed"` (`196` indexed chunks total), and live `context_search` probes confirmed all four critical tokens (`ROUND_HALF_EVEN`, `hmac.compare_digest`, `v1=`, `Decimal | str | int`) remain intact (`True` on every check).

## 3. Cross-Machine 3-Agent Handoff (`data/handoff_report.json`)

The ADLC workflow splits across three distinct models and two hosts linked through Meko `run_id = aa0058c5affc4a17b857c03705d25df9`:

1. **Agent 1 (`claude-code-architect`, Mac mini)**:
   - Conversation `aa0058c5affc4a17b857c03705d25df9` searched ADRs, drafted PostgreSQL migration `0003_add_refund_ledger.sql` (`1,255` bytes, `verifier.passed=true`), saved and promoted collective memory `3ab4a2a2-1262-4844-8bc0-4c00a4c9d467`, uploaded the SQL artifact (`sha256=069ba98c439b7d76...`), and logged `1062` input / `316` output tokens.
2. **Agent 2 (`codex-verifier`, MacBook Pro `codex exec -s read-only`)**:
   - Conversation `58a8e4ff0f8448aaa0eed0bf60c5914c` started with `run_id=aa0058c5affc4a17b857c03705d25df9` and zero local chat history, retrieved Agent 1's SQL artifact across agents (`artifact_access_mode="cross_agent"`), passed `sql_constraint` validation, and generated a Python SQL lock-safety verifier in `100.176s` (`1363` in / `3975` out tokens).
3. **Agent 3 (`pr-review-drift-guard`, DeepSeek V4.1 Flash)**:
   - Conversation `5d443d7ca2ed4991b30d7de0e0dc7103` audited a drifted PR diff (`bad_pr.py`) against retrieved ADRs and promoted memories, catching all `5` deterministic AST/regex violations plus 2 additional grounded violations, uploaded `pr_drift_audit_report.json` (`7,557` bytes, artifact `de85f226-9a55-4d08-bb2e-af7c13ace911`), and included `explain_this_decision_under_2min` for non-technical sign-off.

## 4. AMP Postgres 18 Zero-Copy Branch Verification (`data/amp_report.json`)

Free-tier AMP enforces `max_cores = 0.5` vCPUs across running endpoints, and newly created `*.db.mekodata.ai` endpoints can trigger an 86,400-second Route 53 SOA negative DNS cache inside macOS `mDNSResponder`.

`run_amp_branch_check()` handles both reliably:

1. Provisions cluster `e35a17cf-fa04-4186-a523-24f66c9bb70c` allow-listed to the caller IPv4 (`122.171.16.129/32`).
2. Connects to `main` (`ep-a4495971.db.mekodata.ai:20010`) using direct Route 53 authoritative NS queries (`dig @ns-1243.awsdns-27.org`) passed to `psycopg` via `hostaddr`, seeds `0001_init_ledger.sql` plus account row `CASH_MAIN`, and records `pg_current_wal_lsn()` (`0/15FBEA8`).
3. Calls `amp_branch_create` (`pr-dryrun-1795329172`, `360244b6-0303-42ac-91e1-59c8b07877ba`) **before** tearing down `main` compute (`MEKO-1017` behavior: branches consume `0` vCPU for storage and inherit parent credentials).
4. Attaches compute on fork (`ep-83794afd.db.mekodata.ai:20011`), verifies `PostgreSQL 18.2`, confirms `cow_inherited_account_rows = 1`, runs `0002_journal_lookup_index.sql`, and asserts Postgres enforces `CHECK` constraint rejection on negative `amount_minor` (`negative_amount_check_violation_enforced = true`).
5. Stores `amp_branch_verification.json` (`artifact_id = 208afd18-8283-4c19-9c77-d7728dee4f09`) and deletes the fork compute and branch in a `finally` block, restoring `used_cores = 0`.

## 5. Closed-Loop Self-Learning (`data/selflearning_report.json`)

1. Conversation `db999c1e51da4c48bddcef868cd3cbf7` issued an uncovered query: `"settlement batch cutoff timezone and clearing bank holiday window policy"`, logging `log_id = f1794f9a-c30f-4b92-a2c2-a67408dfee78` with `best_score = 0.3025` (`band = "low"`).
2. `selflearning_status` and `selflearning_shortfalls` surfaced the coverage gap (`category = "coverage"`).
3. Remediation uploaded `ADR-007` and promoted memory covering `21:30:00 UTC` cutoff and TARGET2/ACH holiday roll rules.
4. `selflearning_verify` replayed test prompt `1c96a2af-e863-43d0-96f9-9615087d6937`, lifting `best_score` from `0.3025` (`low`) to `0.8674` (`high`), with `hits_above_mid = 2` and `hint = "The fix helped."`.
