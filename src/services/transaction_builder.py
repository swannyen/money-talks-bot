"""Build complete rows for insert (FX, year, optional yfinance metadata)."""

from __future__ import annotations

from datetime import datetime

from src.config import get_settings
from src.models import ExtractedTransaction
from src.services.fx import try_convert_value_to_base
from src.services.market_data import get_ticker_metadata


def enrich_draft_for_insert(draft: ExtractedTransaction) -> ExtractedTransaction:
    settings = get_settings()
    dt = datetime.strptime(str(draft.date)[:10], "%Y-%m-%d")
    updates: dict = {"year": draft.year or dt.year}

    quantity = draft.quantity if draft.quantity and draft.quantity > 0 else 1
    updates["quantity"] = quantity

    value = float(draft.value)  # type: ignore[arg-type]
    currency = str(draft.currency).upper()

    if draft.value_base is None:
        converted = try_convert_value_to_base(value, currency, settings.base_currency)
        if converted is not None:
            updates["value_base"] = converted
        elif currency == settings.base_currency:
            updates["value_base"] = value
        else:
            updates["value_base"] = None
            note = draft.notes or ""
            fx_note = (
                f"FX conversion unavailable ({currency}->{settings.base_currency}); "
                "value_base left empty"
            )
            if fx_note not in note:
                updates["notes"] = f"{note} | {fx_note}".strip(" |")
    if draft.price_per_unit is None:
        base_val = updates.get("value_base", draft.value_base)
        if base_val is not None:
            updates["price_per_unit"] = float(base_val) / quantity

    ticker = (draft.ticker or "").strip()
    if ticker and ticker.upper() != "NA" and not draft.asset_name:
        meta = get_ticker_metadata(ticker)
        if meta.get("asset_name"):
            updates["asset_name"] = meta["asset_name"]
        if meta.get("asset_class"):
            updates["asset_class"] = meta["asset_class"]

    return draft.model_copy(update=updates)
