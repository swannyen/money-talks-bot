"""Apply holdings-based enrichment to transaction drafts."""

from __future__ import annotations

from src.models import ExtractedTransaction
from src.services.database import TransactionDatabase
from src.services.holdings import fill_dividend_quantity_from_holdings


def enrich_draft(draft: ExtractedTransaction, db: TransactionDatabase) -> ExtractedTransaction:
    updated = fill_dividend_quantity_from_holdings(draft, db)
    updated.refresh_missing_fields()
    return updated
