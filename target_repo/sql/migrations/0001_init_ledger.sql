-- Baseline ledger schema conforming to ADR-001 and ADR-002
SET lock_timeout = '2s';
SET statement_timeout = '30s';

CREATE TABLE IF NOT EXISTS ledger_accounts (
    account_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL,
    currency CHAR(3) NOT NULL,
    account_code TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, account_code)
);

CREATE TABLE IF NOT EXISTS journal_entries (
    entry_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    idempotency_key VARCHAR(128) NOT NULL,
    currency CHAR(3) NOT NULL,
    request_hash CHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS journal_lines (
    line_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entry_id BIGINT NOT NULL REFERENCES journal_entries(entry_id),
    tenant_id TEXT NOT NULL,
    account_id UUID NOT NULL REFERENCES ledger_accounts(account_id),
    direction TEXT NOT NULL,
    amount_minor BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE journal_lines
    ADD CONSTRAINT chk_journal_line_positive CHECK (amount_minor > 0) NOT VALID;
ALTER TABLE journal_lines
    VALIDATE CONSTRAINT chk_journal_line_positive;

ALTER TABLE journal_lines
    ADD CONSTRAINT chk_journal_line_direction CHECK (direction IN ('DEBIT', 'CREDIT')) NOT VALID;
ALTER TABLE journal_lines
    VALIDATE CONSTRAINT chk_journal_line_direction;
