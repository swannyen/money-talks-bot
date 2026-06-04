"""Strict JSON schema returned by the vision LLM."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class VisionTransactionLine(BaseModel):
    """One row from a broker activity / history screenshot."""

    line_type: Literal[
        "cash_dividend",
        "dividend_tax",
        "buy",
        "sell",
        "deposit",
        "withdrawal",
        "fee",
        "other",
    ] = "other"
    action: Optional[Literal["BUY", "SELL", "DIVIDEND", "DEPOSIT", "FEE"]] = None
    date: Optional[str] = None  # YYYY-MM-DD
    time: Optional[str] = None
    ticker: Optional[str] = None
    asset_name: Optional[str] = None
    amount: Optional[float] = None  # positive number (magnitude)
    amount_sign: Optional[Literal["+", "-"]] = None
    currency: Optional[str] = None
    quantity: Optional[int] = None


class VisionExtractionResult(BaseModel):
    """Table-style dividend export (single row) or wrapper with activity lines."""

    screen_type: Literal[
        "dividend_table",
        "activity_feed",
        "dividend",
        "buy",
        "sell",
        "deposit",
        "fee",
        "unknown",
    ] = "unknown"
    transactions: list[VisionTransactionLine] = Field(default_factory=list)
    # Legacy single-row table fields (Tiger web dividend table)
    date: Optional[str] = None
    portfolio: Optional[str] = None
    action: Optional[Literal["BUY", "SELL", "DIVIDEND", "DEPOSIT", "FEE"]] = None
    ticker: Optional[str] = None
    asset_name: Optional[str] = None
    quantity: Optional[int] = None
    currency: Optional[str] = None
    cash_dividends: Optional[float] = None
    net_cash_value: Optional[float] = None
    fees_tax: Optional[float] = None
    trade_value: Optional[float] = None
    value: Optional[float] = None
    confidence_score: float = Field(ge=0.0, le=1.0, default=0.5)
    missing_fields: list[str] = Field(default_factory=list)
    notes: Optional[str] = None
