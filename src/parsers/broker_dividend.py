"""Parse broker dividend exports (Tiger, MooMoo, etc.)."""

from __future__ import annotations

import re
from typing import Optional

import pandas as pd

from src.models import ExtractedTransaction
from src.parsers.common import (
    build_header_map,
    normalize_header,
    parse_date,
    parse_float,
)

BROKER_DIVIDEND_HEADERS: dict[str, list[str]] = {
    "date": ["date"],
    "symbol": ["symbol"],
    "product": ["product"],
    "quantity_gross_rate": ["quantity/gross rate", "quantity gross rate"],
    "phase": ["phase"],
    "cash_dividends": ["cash dividends", "cash dividend"],
    "shares": ["shares"],
    "fees_tax": ["fees & tax", "fees and tax", "fees tax"],
    "net_cash_value": ["net cash value", "net cash"],
    "currency": ["currency", "ccy"],
}


def is_broker_dividend_export(columns: list[str]) -> bool:
    """Tiger-style dividend CSV has Cash Dividends / Net Cash Value, not Action."""
    normalized = {normalize_header(column) for column in columns}
    has_dividend_cols = bool(
        normalized
        & {
            "cash dividends",
            "cash dividend",
            "net cash value",
            "net cash",
        }
    )
    return has_dividend_cols and "action" not in normalized


def parse_ticker_from_symbol(text: str) -> tuple[Optional[str], Optional[str]]:
    """'Visa\\n(V)' -> ('V', 'Visa')."""
    if not text or pd.isna(text):
        return None, None
    raw = str(text).strip()
    match = re.search(r"\(([^)]+)\)", raw)
    if match:
        ticker = match.group(1).strip().upper()
        name = re.sub(r"\([^)]*\)", "", raw).strip()
        name = re.sub(r"\s+", " ", name) or None
        return ticker, name
    token = raw.split()[0].strip().upper() if raw else None
    return token, raw or None


def parse_quantity_gross_rate(text: str) -> tuple[Optional[int], Optional[float]]:
    if not text or pd.isna(text):
        return None, None
    raw = str(text)
    qty_match = re.search(r"quantity:\s*([\d.]+)", raw, re.IGNORECASE)
    rate_match = re.search(r"gross\s*rate:\s*([\d.]+)", raw, re.IGNORECASE)
    quantity = int(float(qty_match.group(1))) if qty_match else None
    rate = float(rate_match.group(1)) if rate_match else None
    return quantity, rate


def parse_fee_amount(text: str) -> Optional[float]:
    if not text or pd.isna(text):
        return None
    match = re.search(
        r"(?:dividend\s+tax|tax|fee)[:\s]*([\d.]+)",
        str(text),
        re.IGNORECASE,
    )
    return float(match.group(1)) if match else parse_float(text)


def _row_to_dividend_draft(
    row: pd.Series, header_map: dict[str, str], row_index: int
) -> ExtractedTransaction:
    def get(field: str):
        col = header_map.get(field)
        return row[col] if col else None

    symbol_raw = get("symbol")
    ticker, asset_name = parse_ticker_from_symbol(str(symbol_raw) if symbol_raw is not None else "")
    quantity, gross_rate = parse_quantity_gross_rate(str(get("quantity_gross_rate") or ""))

    cash_dividends = parse_float(get("cash_dividends"))
    net_cash = parse_float(get("net_cash_value"))
    fees = parse_fee_amount(get("fees_tax"))
    value = net_cash if net_cash is not None else cash_dividends

    note_parts = ["Broker dividend export"]
    if cash_dividends is not None:
        note_parts.append(f"Gross: {cash_dividends}")
    if fees is not None:
        note_parts.append(f"Tax/fees: {fees}")
    if net_cash is not None:
        note_parts.append(f"Net: {net_cash}")
    if gross_rate is not None:
        note_parts.append(f"Gross rate: {gross_rate}/share")
    if value is not None:
        note_parts.append("Value uses net cash (edit value for gross)")

    draft = ExtractedTransaction(
        date=parse_date(get("date")) or "",
        portfolio=None,
        action="DIVIDEND",
        ticker=ticker,
        asset_name=asset_name,
        quantity=quantity,
        currency=(str(get("currency")).strip().upper() if pd.notna(get("currency")) else None),
        value=value,
        confidence_score=1.0,
        source="spreadsheet",
        notes=f"Row {row_index + 1} | " + " | ".join(note_parts),
    )
    draft.refresh_missing_fields()
    return draft


def parse_broker_dividend_dataframe(df: pd.DataFrame) -> list[ExtractedTransaction]:
    header_map = build_header_map(list(df.columns), BROKER_DIVIDEND_HEADERS)
    required = {"date", "symbol", "currency"}
    missing = required - set(header_map)
    if missing:
        raise ValueError(
            "Broker dividend CSV missing columns: "
            + ", ".join(sorted(missing))
            + f". Found: {', '.join(df.columns.astype(str))}"
        )
    if "net_cash_value" not in header_map and "cash_dividends" not in header_map:
        raise ValueError("Broker dividend CSV needs 'Net Cash Value' or 'Cash Dividends' column.")

    drafts: list[ExtractedTransaction] = []
    for idx, row in df.iterrows():
        if pd.isna(row.get(header_map["date"])):
            continue
        draft = _row_to_dividend_draft(row, header_map, int(idx))
        if not draft.date and not draft.ticker:
            continue
        drafts.append(draft)
    return drafts
