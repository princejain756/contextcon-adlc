-- migrate:no-transaction (NO_TX)
SET lock_timeout = '2s';
SET statement_timeout = '30s';

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_journal_lines_tenant_entry
    ON journal_lines (tenant_id, entry_id);
