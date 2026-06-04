from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from src.models import ExtractedTransaction
from src.services.database import TransactionDatabase


@dataclass
class DuplicateCheckResult:
    has_duplicates: bool
    matches: pd.DataFrame


def check_duplicates(
    draft: ExtractedTransaction,
    db: TransactionDatabase,
    *,
    tolerance: float = 0.01,
) -> DuplicateCheckResult:
    if not draft.is_ready_for_confirmation():
        return DuplicateCheckResult(has_duplicates=False, matches=pd.DataFrame())

    tx_date = datetime.strptime(str(draft.date)[:10], "%Y-%m-%d")
    matches = db.find_similar(
        date=tx_date,
        portfolio=str(draft.portfolio),
        ticker=str(draft.ticker),
        action=str(draft.action),
        currency=str(draft.currency),
        value=float(draft.value),  # type: ignore[arg-type]
        tolerance=tolerance,
    )
    return DuplicateCheckResult(has_duplicates=not matches.empty, matches=matches)


def format_duplicate_warning(result: DuplicateCheckResult) -> str:
    if not result.has_duplicates:
        return ""
    lines = [
        "⚠️ *Possible duplicate* — similar row(s) already in the database:",
        "",
    ]
    for _, row in result.matches.iterrows():
        lines.append(
            f"• id `{row['id']}` — {row['date']} | {row['action']} | "
            f"{row['ticker']} | {row['value']} {row['currency']}"
        )
    lines.extend(["", "Reply `confirm anyway` to save, or `reject`."])
    return "\n".join(lines)
