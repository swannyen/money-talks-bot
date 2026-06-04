"""Map vision LLM JSON to ExtractedTransaction drafts."""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime
from typing import Optional

import pandas as pd

from src.models import ExtractedTransaction
from src.parsers.vision_schema import VisionExtractionResult, VisionTransactionLine

DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d")


def normalize_date(date_str: Optional[str]) -> str:
    if not date_str:
        return ""
    raw = str(date_str).strip()
    if " " in raw:
        raw = raw.split()[0]
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    try:
        return pd_timestamp_to_date(raw)
    except (TypeError, ValueError):
        return raw[:10] if len(raw) >= 10 else raw


def pd_timestamp_to_date(raw: str) -> str:
    return pd.to_datetime(raw).strftime("%Y-%m-%d")


def _parse_ticker_asset(text: str) -> tuple[Optional[str], Optional[str]]:
    """'AAPL Apple' -> ('AAPL', 'Apple')."""
    raw = text.strip()
    if not raw:
        return None, None
    parts = raw.split(None, 1)
    ticker = parts[0].strip().upper()
    name = parts[1].strip() if len(parts) > 1 else None
    match = re.search(r"\(([^)]+)\)", raw)
    if match:
        ticker = match.group(1).strip().upper()
        name = re.sub(r"\([^)]*\)", "", raw).strip() or name
    return ticker, name


def _line_action(line: VisionTransactionLine) -> str:
    if line.action:
        return line.action
    mapping = {
        "cash_dividend": "DIVIDEND",
        "dividend_tax": "FEE",
        "buy": "BUY",
        "sell": "SELL",
        "deposit": "DEPOSIT",
        "fee": "FEE",
    }
    return mapping.get(line.line_type, "DIVIDEND")


def _line_amount(line: VisionTransactionLine) -> Optional[float]:
    if line.amount is None:
        return None
    amt = abs(float(line.amount))
    if line.amount_sign == "-":
        return amt
    if line.line_type == "dividend_tax":
        return amt
    return amt


def _line_to_draft(
    line: VisionTransactionLine,
    *,
    value: Optional[float] = None,
    action: Optional[str] = None,
    extra_notes: Optional[str] = None,
    confidence: float = 0.85,
) -> ExtractedTransaction:
    ticker = (line.ticker or "").strip().upper() or None
    asset_name = line.asset_name
    if ticker and asset_name:
        asset_name = asset_name.strip()
    elif ticker:
        ticker, asset_name = _parse_ticker_asset(ticker)
    elif asset_name:
        ticker, asset_name = _parse_ticker_asset(asset_name)

    resolved_action = action or _line_action(line)
    resolved_value = value if value is not None else _line_amount(line)

    notes = extra_notes or ""
    if line.time:
        notes = f"{notes} | Time: {line.time}".strip(" |")

    draft = ExtractedTransaction(
        date=normalize_date(line.date),
        portfolio=None,
        action=resolved_action,  # type: ignore[arg-type]
        ticker=ticker,
        asset_name=asset_name,
        quantity=line.quantity,
        currency=line.currency,
        value=resolved_value,
        confidence_score=confidence,
        notes=notes or None,
        source="vision",
    )
    draft.refresh_missing_fields()
    return draft


def _group_key(line: VisionTransactionLine) -> tuple[str, str]:
    ticker = (line.ticker or "").upper()
    if not ticker and line.asset_name:
        ticker, _ = _parse_ticker_asset(line.asset_name)
    return (ticker or "UNKNOWN", normalize_date(line.date))


def consolidate_activity_feed(
    lines: list[VisionTransactionLine],
) -> list[ExtractedTransaction]:
    """Merge Cash Dividend + Dividend Tax on same ticker/date into one DIVIDEND draft."""
    by_key: dict[tuple[str, str], list[VisionTransactionLine]] = defaultdict(list)
    other: list[VisionTransactionLine] = []

    for line in lines:
        if line.line_type in ("cash_dividend", "dividend_tax"):
            by_key[_group_key(line)].append(line)
        else:
            other.append(line)

    drafts: list[ExtractedTransaction] = []

    for _key, group in by_key.items():
        cash_lines = [ln for ln in group if ln.line_type == "cash_dividend"]
        tax_lines = [ln for ln in group if ln.line_type == "dividend_tax"]

        if cash_lines and tax_lines:
            cash = cash_lines[0]
            tax = tax_lines[0]
            gross = _line_amount(cash) or 0.0
            tax_amt = _line_amount(tax) or 0.0
            net = round(gross - tax_amt, 4)
            notes = (
                f"Tiger activity feed | Gross dividend: +{gross} | "
                f"Dividend tax: -{tax_amt} | Net: {net} | "
                f"Use `edit value {gross}` to record gross instead"
            )
            drafts.append(
                _line_to_draft(
                    cash,
                    value=net,
                    action="DIVIDEND",
                    extra_notes=notes,
                )
            )
        elif cash_lines:
            drafts.append(_line_to_draft(cash_lines[0]))
        elif tax_lines:
            drafts.append(_line_to_draft(tax_lines[0]))

    for line in other:
        drafts.append(_line_to_draft(line))

    return drafts


def vision_result_to_draft(result: VisionExtractionResult) -> ExtractedTransaction:
    action = result.action
    if not action and result.screen_type in ("dividend", "dividend_table"):
        action = "DIVIDEND"

    value = result.value
    value_source = "explicit value"
    if value is None:
        if result.net_cash_value is not None:
            value = result.net_cash_value
            value_source = "net cash value (after tax)"
        elif result.cash_dividends is not None:
            value = result.cash_dividends
            value_source = "cash dividends (gross)"
        elif result.trade_value is not None:
            value = result.trade_value
            value_source = "trade amount"

    note_parts: list[str] = []
    if result.notes:
        note_parts.append(result.notes)
    if result.cash_dividends is not None:
        note_parts.append(f"Gross dividends: {result.cash_dividends}")
    if result.fees_tax is not None:
        note_parts.append(f"Tax/fees: {result.fees_tax}")
    if result.net_cash_value is not None:
        note_parts.append(f"Net cash: {result.net_cash_value}")
    if value is not None:
        note_parts.append(f"Value field uses {value_source}")
        if result.cash_dividends is not None and result.net_cash_value is not None:
            note_parts.append("Use `edit value` to switch gross vs net")

    draft = ExtractedTransaction(
        date=normalize_date(result.date),
        portfolio=result.portfolio,
        action=action,
        ticker=result.ticker,
        asset_name=result.asset_name,
        quantity=result.quantity,
        currency=result.currency,
        value=value,
        confidence_score=result.confidence_score,
        notes=" | ".join(note_parts) if note_parts else None,
        source="vision",
    )
    draft.refresh_missing_fields()
    for field in result.missing_fields:
        if field not in draft.missing_fields:
            draft.missing_fields.append(field)
    draft.missing_fields = sorted(set(draft.missing_fields))
    return draft


def parse_vision_payload(raw: dict) -> list[ExtractedTransaction]:
    """Return one or more drafts (activity feed may consolidate dividend + tax)."""
    result = VisionExtractionResult.model_validate(raw)

    if result.transactions:
        if result.screen_type == "activity_feed" or _is_activity_dividend_feed(result.transactions):
            drafts = consolidate_activity_feed(result.transactions)
        else:
            drafts = [_line_to_draft(line) for line in result.transactions]

        for draft in drafts:
            for field in result.missing_fields:
                if field not in draft.missing_fields:
                    draft.missing_fields.append(field)
            draft.missing_fields = sorted(set(draft.missing_fields))
            if not result.portfolio and "portfolio" not in draft.missing_fields:
                draft.missing_fields.append("portfolio")
        return drafts

    return [vision_result_to_draft(result)]


def _is_activity_dividend_feed(lines: list[VisionTransactionLine]) -> bool:
    types = {line.line_type for line in lines}
    return bool(types & {"cash_dividend", "dividend_tax"})
