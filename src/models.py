from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from src.config import ACCEPTED_ACTIONS, get_settings

ActionType = Literal["FEE", "BUY", "SELL", "DIVIDEND", "DEPOSIT"]


class ExtractedTransaction(BaseModel):
    """Draft from parser (spreadsheet, LLM, or manual) before DB mapping."""

    date: str  # YYYY-MM-DD preferred
    portfolio: Optional[str] = None
    action: Optional[ActionType] = None
    ticker: Optional[str] = None
    quantity: Optional[int] = None
    currency: Optional[str] = None
    value: Optional[float] = None
    asset_name: Optional[str] = None
    asset_class: Optional[str] = None
    value_base: Optional[float] = None
    price_per_unit: Optional[float] = None
    year: Optional[int] = None
    confidence_score: float = 1.0
    missing_fields: list[str] = Field(default_factory=list)
    notes: Optional[str] = None
    source: str = "unknown"  # spreadsheet | manual | vision

    def required_field_names(self) -> list[str]:
        missing = []
        if not self.date:
            missing.append("date")
        if not self.portfolio:
            missing.append("portfolio")
        if not self.action:
            missing.append("action")
        if not self.ticker:
            missing.append("ticker")
        if self.currency is None:
            missing.append("currency")
        if self.value is None:
            missing.append("value")
        return missing

    def refresh_missing_fields(self) -> None:
        self.missing_fields = self.required_field_names()

    def is_ready_for_confirmation(self) -> bool:
        self.refresh_missing_fields()
        return len(self.missing_fields) == 0

    @field_validator("portfolio")
    @classmethod
    def validate_portfolio_when_set(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        allowed = get_settings().portfolios
        if value not in allowed:
            raise ValueError(f"Portfolio must be one of: {', '.join(allowed)}")
        return value

    @field_validator("currency")
    @classmethod
    def validate_currency_when_set(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip().upper()
        allowed = get_settings().currencies
        if normalized not in allowed:
            raise ValueError(f"Currency must be one of: {', '.join(allowed)}")
        return normalized

    @field_validator("action")
    @classmethod
    def validate_action_when_set(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        upper = value.strip().upper()
        if upper not in ACCEPTED_ACTIONS:
            raise ValueError(f"Action must be one of: {', '.join(ACCEPTED_ACTIONS)}")
        return upper  # type: ignore[return-value]


class PendingTransaction(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    chat_id: int
    draft: ExtractedTransaction
    created_at: datetime = Field(default_factory=datetime.utcnow)
    row_index: Optional[int] = None  # position in uploaded spreadsheet batch
