from __future__ import annotations

from collections.abc import Callable

from src.config import Settings, get_settings
from src.messages import portfolio_edit_hints
from src.models import ExtractedTransaction, PendingTransaction

HintBuilder = Callable[[ExtractedTransaction, Settings], list[str]]


def _hint_portfolio(_draft: ExtractedTransaction, settings: Settings) -> list[str]:
    return portfolio_edit_hints(settings.portfolios)


def _hint_currency(_draft: ExtractedTransaction, settings: Settings) -> list[str]:
    return [f"• `edit currency {code}`" for code in settings.currencies]


def _hint_ticker(draft: ExtractedTransaction, _settings: Settings) -> list[str]:
    return [f"• `edit ticker {draft.ticker or 'V'}`"]


def _hint_quantity(draft: ExtractedTransaction, _settings: Settings) -> list[str]:
    qty = draft.quantity if draft.quantity is not None else 1
    return [f"• `edit quantity {qty}`"]


def _hint_value(draft: ExtractedTransaction, _settings: Settings) -> list[str]:
    if draft.value is not None:
        return [f"• `edit value {draft.value}`"]
    return ["• `edit value <amount>`"]


_MISSING_FIELD_HINTS: dict[str, HintBuilder] = {
    "portfolio": _hint_portfolio,
    "date": lambda _d, _s: ["• `edit date 2026-06-01`"],
    "action": lambda _d, _s: ["• `edit action DIVIDEND`"],
    "ticker": _hint_ticker,
    "currency": _hint_currency,
    "quantity": _hint_quantity,
    "value": _hint_value,
}


def _optional_value_hint(draft: ExtractedTransaction, _settings: Settings) -> list[str]:
    if draft.value is None or "value" in draft.missing_fields:
        return []
    return [f"• `edit value {draft.value}` — change amount"]


def _optional_portfolio_hints(draft: ExtractedTransaction, settings: Settings) -> list[str]:
    if not draft.portfolio or "portfolio" in draft.missing_fields:
        return []
    return [f"• `edit portfolio {name}`" for name in settings.portfolios if name != draft.portfolio]


def _optional_ticker_hint(draft: ExtractedTransaction, _settings: Settings) -> list[str]:
    if not draft.ticker or "ticker" in draft.missing_fields:
        return []
    return [f"• `edit ticker {draft.ticker}`"]


_OPTIONAL_HINTS: tuple[HintBuilder, ...] = (
    _optional_value_hint,
    _optional_portfolio_hints,
    _optional_ticker_hint,
)


def _format_reply_hints(draft: ExtractedTransaction) -> list[str]:
    """Contextual edit examples using PORTFOLIOS / CURRENCIES from .env."""
    settings = get_settings()
    hints = ["• `confirm`", "• `reject`"]

    for field in draft.missing_fields:
        builder = _MISSING_FIELD_HINTS.get(field)
        if builder:
            hints.extend(builder(draft, settings))

    for builder in _OPTIONAL_HINTS:
        hints.extend(builder(draft, settings))

    return hints


def format_transaction_summary(draft: ExtractedTransaction, *, title: str = "Transaction") -> str:
    settings = get_settings()
    lines = [
        f"📋 *{title}*",
        "",
        f"*Date:* {draft.date or '—'}",
        f"*Portfolio:* {draft.portfolio or '—'}",
        f"*Action:* {draft.action or '—'}",
        f"*Ticker:* {draft.ticker or '—'}",
        f"*Quantity:* {draft.quantity if draft.quantity is not None else '—'}",
        f"*Currency:* {draft.currency or '—'}",
        f"*Value:* {draft.value if draft.value is not None else '—'}",
    ]
    if draft.asset_name:
        lines.append(f"*Asset name:* {draft.asset_name}")
    if draft.source == "vision":
        lines.append(f"*Confidence:* {draft.confidence_score:.0%}")
    if draft.notes:
        lines.append(f"*Notes:* {draft.notes}")
    if draft.missing_fields:
        lines.append("")
        lines.append(f"⚠️ Still needed: {', '.join(draft.missing_fields)}")
    if "portfolio" in draft.missing_fields:
        if settings.portfolios:
            lines.append(f"*Portfolios (from your .env):* {', '.join(settings.portfolios)}")
        else:
            lines.append(
                "*Portfolio:* set via `edit portfolio <name>` (configure `PORTFOLIOS` in `.env`)"
            )
    lines.append("")
    lines.append("Reply:")
    lines.extend(_format_reply_hints(draft))
    return "\n".join(lines)


def format_pending_list(pending: list[PendingTransaction]) -> str:
    if not pending:
        return "No pending transactions."
    lines = ["*Pending confirmations:*", ""]
    for idx, item in enumerate(pending, start=1):
        d = item.draft
        label = f"{d.date} | {d.action} | {d.ticker} | {d.value} {d.currency}"
        lines.append(f"{idx}. `{item.id[:8]}` — {label}")
    lines.append("")
    lines.append("Confirm the active draft, or upload a new file.")
    return "\n".join(lines)
