"""Double-entry financial ledger engine conforming to ADR-002."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_EVEN
from typing import Iterable

from ledger_service.errors import IdempotencyConflictError, UnbalancedJournalError, ValidationError


@dataclass(frozen=True)
class PostingLine:
    account_id: str
    direction: str  # "DEBIT" or "CREDIT"
    amount_minor: int

    def __post_init__(self) -> None:
        if not self.account_id or not self.account_id.strip():
            raise ValidationError("account_id is required")
        if self.direction not in ("DEBIT", "CREDIT"):
            raise ValidationError(f"Invalid direction: {self.direction}")
        if not isinstance(self.amount_minor, int) or isinstance(self.amount_minor, bool) or self.amount_minor <= 0:
            raise ValidationError("amount_minor must be a positive integer in minor currency units")


@dataclass(frozen=True)
class JournalEntry:
    entry_id: str
    tenant_id: str
    idempotency_key: str
    currency: str
    lines: tuple[PostingLine, ...]
    request_hash: str


def compute_fee_minor(amount_minor: int, rate_bps: Decimal | str | int) -> int:
    """Compute basis-points fee using Decimal ROUND_HALF_EVEN with zero floats."""
    if not isinstance(amount_minor, int) or isinstance(amount_minor, bool) or amount_minor < 0:
        raise ValidationError("amount_minor must be a non-negative integer")
    if isinstance(rate_bps, float):
        raise ValidationError("float rates are prohibited by ADR-002; pass Decimal, str, or int")
    dec_bps = rate_bps if isinstance(rate_bps, Decimal) else Decimal(str(rate_bps))
    raw_fee = (Decimal(amount_minor) * dec_bps) / Decimal("10000")
    rounded = raw_fee.quantize(Decimal("1"), rounding=ROUND_HALF_EVEN)
    return int(rounded)


def validate_balanced_lines(lines: Iterable[PostingLine]) -> tuple[PostingLine, ...]:
    line_tuple = tuple(lines)
    if len(line_tuple) < 2:
        raise UnbalancedJournalError("Double-entry journal requires at least 2 posting lines")
    debit_total = sum(ln.amount_minor for ln in line_tuple if ln.direction == "DEBIT")
    credit_total = sum(ln.amount_minor for ln in line_tuple if ln.direction == "CREDIT")
    if debit_total <= 0 or debit_total != credit_total:
        raise UnbalancedJournalError(f"Unbalanced journal: debits={debit_total} credits={credit_total}")
    return line_tuple


def compute_request_hash(tenant_id: str, operation: str, currency: str, lines: tuple[PostingLine, ...]) -> str:
    canonical = {
        "tenant_id": tenant_id,
        "operation": operation,
        "currency": currency.upper(),
        "lines": [
            {"account_id": ln.account_id, "direction": ln.direction, "amount_minor": ln.amount_minor}
            for ln in sorted(lines, key=lambda x: (x.account_id, x.direction, x.amount_minor))
        ],
    }
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class InMemoryLedgerStore:
    """Deterministic ledger journal store scoped by (tenant_id, idempotency_key)."""

    def __init__(self) -> None:
        self._entries: dict[tuple[str, str], JournalEntry] = {}
        self._seq: int = 0

    def post_journal(
        self,
        tenant_id: str,
        idempotency_key: str,
        currency: str,
        lines: Iterable[PostingLine],
    ) -> tuple[JournalEntry, bool]:
        if not tenant_id or not tenant_id.strip():
            raise ValidationError("tenant_id is required")
        cleaned_key = (idempotency_key or "").strip()
        if not cleaned_key or len(cleaned_key) > 128:
            raise ValidationError("idempotency_key must be non-empty and <= 128 chars")
        if not currency or len(currency.strip()) != 3:
            raise ValidationError("currency must be an ISO-4217 3-letter code")

        checked_lines = validate_balanced_lines(lines)
        req_hash = compute_request_hash(tenant_id.strip(), "post_journal", currency.strip().upper(), checked_lines)
        cache_key = (tenant_id.strip(), cleaned_key)

        existing = self._entries.get(cache_key)
        if existing is not None:
            if existing.request_hash != req_hash:
                raise IdempotencyConflictError("idempotency_key reused with conflicting payload")
            return existing, True

        self._seq += 1
        entry = JournalEntry(
            entry_id=f"je_{self._seq:06d}",
            tenant_id=tenant_id.strip(),
            idempotency_key=cleaned_key,
            currency=currency.strip().upper(),
            lines=checked_lines,
            request_hash=req_hash,
        )
        self._entries[cache_key] = entry
        return entry, False
