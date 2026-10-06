"""Parse CSV/Excel: Money Talks exports or broker dividend exports (Tiger, etc.)."""

from __future__ import annotations

import io
from typing import BinaryIO

import pandas as pd

from src.models import ExtractedTransaction
from src.parsers.broker_dividend import (
    is_broker_dividend_export,
    parse_broker_dividend_dataframe,
)
from src.parsers.common import build_header_map, parse_date, parse_float, parse_int

MONEY_TALKS_COLUMNS: dict[str, list[str]] = {
    "date": ["date", "transaction date", "tx date"],
    "portfolio": ["portfolio"],
    "ticker": ["ticker", "symbol"],
    "asset_name": ["asset name", "asset_name"],
    "asset_class": ["asset class", "asset_class"],
    "currency": ["currency", "ccy"],
    "action": ["action", "type"],
    "quantity": ["quantity", "qty", "shares"],
    "value": ["value", "amount", "total"],
    "value_base": ["value (base)", "value_base", "value base"],
    "price_per_unit": ["price per unit", "price_per_unit", "price"],
    "year": ["year"],
}


def _row_to_money_talks_draft(
    row: pd.Series, header_map: dict[str, str], row_index: int
) -> ExtractedTransaction:
    def get(field: str):
        col = header_map.get(field)
        return row[col] if col else None

    action_raw = get("action")
    action = str(action_raw).strip().upper() if pd.notna(action_raw) else None
    draft = ExtractedTransaction(
        date=parse_date(get("date")) or "",
        portfolio=str(get("portfolio")).strip() if pd.notna(get("portfolio")) else None,
        ticker=str(get("ticker")).strip() if pd.notna(get("ticker")) else None,
        asset_name=(str(get("asset_name")).strip() if pd.notna(get("asset_name")) else None),
        asset_class=(str(get("asset_class")).strip() if pd.notna(get("asset_class")) else None),
        currency=(str(get("currency")).strip().upper() if pd.notna(get("currency")) else None),
        action=action,  # type: ignore[arg-type]
        quantity=parse_int(get("quantity")),
        value=parse_float(get("value")),
        value_base=parse_float(get("value_base")),
        price_per_unit=parse_float(get("price_per_unit")),
        year=parse_int(get("year")),
        confidence_score=1.0,
        source="spreadsheet",
        notes=f"Row {row_index + 1} from Money Talks export",
    )
    draft.refresh_missing_fields()
    return draft


def load_dataframe(file_obj: BinaryIO, filename: str) -> pd.DataFrame:
    lower = filename.lower()
    if lower.endswith(".csv"):
        return pd.read_csv(file_obj)
    if lower.endswith(".xlsx"):
        return pd.read_excel(file_obj)
    raise ValueError("Unsupported file type. Send .csv or .xlsx")


def parse_spreadsheet_bytes(content: bytes, filename: str) -> list[ExtractedTransaction]:
    buffer = io.BytesIO(content)
    df = load_dataframe(buffer, filename)
    if df.empty:
        return []

    columns = list(df.columns)
    if is_broker_dividend_export(columns):
        return parse_broker_dividend_dataframe(df)

    header_map = build_header_map(columns, MONEY_TALKS_COLUMNS)
    required_for_import = {"date", "portfolio", "action", "ticker", "currency", "value"}
    missing_headers = required_for_import - set(header_map)
    if missing_headers:
        raise ValueError(
            "Could not find required columns: "
            + ", ".join(sorted(missing_headers))
            + f". Found columns: {', '.join(df.columns.astype(str))}"
        )

    drafts: list[ExtractedTransaction] = []
    for idx, row in df.iterrows():
        draft = _row_to_money_talks_draft(row, header_map, int(idx))
        if draft.required_field_names() == ["date"] and not draft.date:
            continue
        if all(
            pd.isna(row.get(header_map.get(field, ""), None))
            for field in ("portfolio", "action", "value")
            if header_map.get(field)
        ):
            continue
        drafts.append(draft)
    return drafts
