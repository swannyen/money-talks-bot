"""Guided step-by-step transaction entry (button + text flow)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

from src.config import ACCEPTED_ACTIONS
from src.models import ExtractedTransaction
from src.parsers.manual import normalize_action, parse_number

# Steps after action is chosen (order matters)
FLOW_STEPS: dict[str, list[str]] = {
    "BUY": ["portfolio", "date", "ticker", "quantity", "currency", "value"],
    "SELL": ["portfolio", "date", "ticker", "quantity", "currency", "value"],
    "DIVIDEND": ["portfolio", "date", "ticker", "quantity", "currency", "value"],
    "FEE": ["portfolio", "date", "ticker", "currency", "value"],
    "DEPOSIT": ["portfolio", "date", "currency", "value"],
}

ACTION_LABELS: dict[str, str] = {
    "BUY": "Buy",
    "SELL": "Sell",
    "DIVIDEND": "Dividend",
    "FEE": "Fee",
    "DEPOSIT": "Deposit",
}

DEPOSIT_TICKER = "NA"

TICKERS_PER_PAGE = 6

TEXT_INPUT_PROMPTS: dict[str, str] = {
    "portfolio": "Type the portfolio name:",
    "date": "Type the date (YYYY-MM-DD or DD/MM/YYYY):",
    "ticker": "Type the ticker symbol (e.g. AAPL, V, BRK.B):",
    "quantity": "Type the quantity (whole number):",
    "value": "Type the amount:",
}


def _chunk_button_rows(
    items: list[tuple[str, str]], *, per_row: int
) -> list[list[tuple[str, str]]]:
    rows: list[list[tuple[str, str]]] = []
    row: list[tuple[str, str]] = []
    for item in items:
        row.append(item)
        if len(row) == per_row:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return rows


def uses_ticker_suggestions(action: Optional[str]) -> bool:
    """Holdings picker with pagination is only for dividend entry."""
    return action == "DIVIDEND"


@dataclass
class GuidedAddState:
    """In-progress guided entry for one chat."""

    draft: ExtractedTransaction = field(
        default_factory=lambda: ExtractedTransaction(date="", source="manual")
    )
    step_index: int = 0
    awaiting_text: Optional[str] = None
    action_chosen: bool = False
    ticker_suggestions: list[tuple[str, str]] = field(default_factory=list)
    ticker_page: int = 0

    @property
    def action(self) -> Optional[str]:
        return self.draft.action

    def current_step(self) -> Optional[str]:
        if not self.action_chosen or not self.draft.action:
            return "action"
        steps = FLOW_STEPS.get(self.draft.action, [])
        if self.step_index >= len(steps):
            return None
        return steps[self.step_index]

    def is_complete(self) -> bool:
        return self.action_chosen and self.current_step() is None


def text_prompt_for_field(field_name: str) -> str:
    return TEXT_INPUT_PROMPTS.get(field_name, f"Type {field_name}:")


def _today_iso() -> str:
    return date.today().isoformat()


def _yesterday_iso() -> str:
    return (date.today() - timedelta(days=1)).isoformat()


def parse_date_input(raw: str) -> str:
    """Return YYYY-MM-DD or raise ValueError."""
    text = raw.strip()
    if text.lower() == "today":
        return _today_iso()
    if text.lower() == "yesterday":
        return _yesterday_iso()
    # YYYY-MM-DD
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return text[:10]
    # DD/MM/YYYY or MM/DD/YYYY — try both via simple split
    for sep in ("/", "-", "."):
        if sep in text:
            parts = text.replace(".", "/").replace("-", "/").split("/")
            if len(parts) == 3:
                a, b, c = (int(p) for p in parts)
                if a > 31:  # YYYY-MM-DD style
                    return f"{a:04d}-{b:02d}-{c:02d}"
                if c < 100:
                    c += 2000
                if a > 12:  # DD/MM
                    return f"{c:04d}-{b:02d}-{a:02d}"
                return f"{c:04d}-{a:02d}-{b:02d}"
    raise ValueError("Use YYYY-MM-DD, DD/MM/YYYY, or type today")


_SIMPLE_STEP_PROMPTS = {
    "action": "What type of transaction do you want to add?",
    "portfolio": "Which portfolio?",
    "date": "Transaction date?",
    "currency": "Currency?",
}

_VALUE_STEP_PROMPTS = {
    "FEE": "Fee amount (positive number)?",
    "DIVIDEND": "Dividend amount (net cash received)?",
    "DEPOSIT": "Deposit amount?",
}


def prompt_for_step(step: Optional[str], *, action: Optional[str] = None) -> str:
    if step == "ticker":
        if action == "DIVIDEND":
            return "Which stock received the dividend? Pick from your holdings or type a symbol:"
        return "Ticker symbol?"
    if step == "quantity":
        if action == "DIVIDEND":
            return "Quantity (shares that received the dividend)?"
        return "Quantity (number of shares)?"
    if step == "value":
        return _VALUE_STEP_PROMPTS.get(action or "", "Total value (amount paid or received)?")
    return _SIMPLE_STEP_PROMPTS.get(step or "", "Review your transaction:")


def build_step_message(state: GuidedAddState) -> str:
    step = state.current_step()
    summary = progress_summary(state)
    prompt = prompt_for_step(step, action=state.action)
    text = f"📝 *Add transaction*\n\n{prompt}"
    if summary:
        text += f"\n\n_{summary}_"
    if step == "ticker":
        if not uses_ticker_suggestions(state.action):
            text += "\n\n_Type the ticker symbol._"
        elif state.ticker_suggestions:
            total_pages = ticker_page_count(len(state.ticker_suggestions))
            if total_pages > 1:
                text += f"\n\n_Holdings page {state.ticker_page + 1} of {total_pages}_"
            text += "\n\n_Tap a holding below, or type a new symbol._"
        else:
            text += "\n\n_No holdings yet for this portfolio — type the ticker._"
    return text


def action_button_rows() -> list[list[tuple[str, str]]]:
    return [
        [
            (ACTION_LABELS["BUY"], "ga:act:BUY"),
            (ACTION_LABELS["SELL"], "ga:act:SELL"),
        ],
        [
            (ACTION_LABELS["DIVIDEND"], "ga:act:DIVIDEND"),
            (ACTION_LABELS["FEE"], "ga:act:FEE"),
        ],
        [(ACTION_LABELS["DEPOSIT"], "ga:act:DEPOSIT")],
        [("Cancel", "ga:cancel")],
    ]


def portfolio_button_rows(portfolios: list[str]) -> list[list[tuple[str, str]]]:
    if not portfolios:
        return [[("Type portfolio name…", "ga:text:portfolio")], [("Cancel", "ga:cancel")]]
    rows = _chunk_button_rows(
        [(name, f"ga:pf:{index}") for index, name in enumerate(portfolios)],
        per_row=2,
    )
    rows.append([("Cancel", "ga:cancel")])
    return rows


def date_button_rows() -> list[list[tuple[str, str]]]:
    return [
        [("Today", "ga:dt:today"), ("Yesterday", "ga:dt:yesterday")],
        [("Type a date…", "ga:text:date")],
        [("Cancel", "ga:cancel")],
    ]


def currency_button_rows(currencies: list[str]) -> list[list[tuple[str, str]]]:
    rows = _chunk_button_rows([(code, f"ga:ccy:{code}") for code in currencies], per_row=3)
    rows.append([("Cancel", "ga:cancel")])
    return rows


def quantity_button_rows(*, action: str) -> list[list[tuple[str, str]]]:
    if action == "DIVIDEND":
        return [
            [("Skip quantity", "ga:qty:skip"), ("Type quantity…", "ga:text:quantity")],
            [("Cancel", "ga:cancel")],
        ]
    return [[("Type quantity…", "ga:text:quantity")], [("Cancel", "ga:cancel")]]


def ticker_page_count(suggestion_count: int) -> int:
    if suggestion_count <= 0:
        return 0
    return (suggestion_count + TICKERS_PER_PAGE - 1) // TICKERS_PER_PAGE


def ticker_button_rows(
    *,
    suggestions: list[tuple[str, str]],
    page: int = 0,
    include_suggestions: bool = True,
) -> list[list[tuple[str, str]]]:
    rows: list[list[tuple[str, str]]] = []
    if include_suggestions and suggestions:
        start = page * TICKERS_PER_PAGE
        page_items = suggestions[start : start + TICKERS_PER_PAGE]
        items = [
            (label, f"ga:tick:{start + offset}")
            for offset, (_ticker, label) in enumerate(page_items)
        ]
        rows.extend(_chunk_button_rows(items, per_row=2))

        total_pages = ticker_page_count(len(suggestions))
        if total_pages > 1:
            nav: list[tuple[str, str]] = []
            if page > 0:
                nav.append(("◀ Prev", "ga:tpg:prev"))
            if page < total_pages - 1:
                nav.append(("Next ▶", "ga:tpg:next"))
            rows.append(nav)

    rows.append([("Type ticker…", "ga:text:ticker")])
    rows.append([("Cancel", "ga:cancel")])
    return rows


def change_ticker_page(state: GuidedAddState, delta: int) -> GuidedAddState:
    total_pages = ticker_page_count(len(state.ticker_suggestions))
    if total_pages <= 1:
        return state
    next_page = max(0, min(state.ticker_page + delta, total_pages - 1))
    state.ticker_page = next_page
    return state


def value_button_rows() -> list[list[tuple[str, str]]]:
    return [[("Type amount…", "ga:text:value")], [("Cancel", "ga:cancel")]]


def confirm_reject_button_rows() -> list[list[tuple[str, str]]]:
    return [
        [("✅ Confirm", "ga:save:confirm"), ("❌ Reject", "ga:save:reject")],
    ]


def buttons_for_step(
    step: Optional[str],
    *,
    portfolios: list[str],
    currencies: list[str],
    action: Optional[str] = None,
    ticker_suggestions: list[tuple[str, str]] | None = None,
    ticker_page: int = 0,
) -> list[list[tuple[str, str]]]:
    if step == "action":
        return action_button_rows()
    if step == "portfolio":
        return portfolio_button_rows(portfolios)
    if step == "date":
        return date_button_rows()
    if step == "ticker":
        return ticker_button_rows(
            suggestions=ticker_suggestions or [],
            page=ticker_page,
            include_suggestions=uses_ticker_suggestions(action),
        )
    if step == "quantity":
        return quantity_button_rows(action=action or "")
    if step == "currency":
        return currency_button_rows(currencies)
    if step == "value":
        return value_button_rows()
    return []


def apply_action(state: GuidedAddState, action: str) -> tuple[GuidedAddState, Optional[str]]:
    normalized = normalize_action(action)
    if normalized not in ACCEPTED_ACTIONS:
        return state, f"Unknown action: {action}"
    updates: dict = {"action": normalized}
    if normalized == "DEPOSIT":
        updates["ticker"] = DEPOSIT_TICKER
    state.draft = state.draft.model_copy(update=updates)  # type: ignore[arg-type]
    state.action_chosen = True
    state.step_index = 0
    state.awaiting_text = None
    return state, None


def apply_portfolio(state: GuidedAddState, portfolio: str) -> tuple[GuidedAddState, Optional[str]]:
    try:
        state.draft = state.draft.model_copy(update={"portfolio": portfolio.strip()})
        state.draft.refresh_missing_fields()
    except ValueError as exc:
        return state, str(exc)
    state.step_index += 1
    state.awaiting_text = None
    return state, None


def apply_date(state: GuidedAddState, date_str: str) -> tuple[GuidedAddState, Optional[str]]:
    try:
        iso = parse_date_input(date_str)
    except (ValueError, TypeError) as exc:
        return state, str(exc)
    state.draft = state.draft.model_copy(update={"date": iso})
    state.step_index += 1
    state.awaiting_text = None
    return state, None


def set_ticker_suggestions(state: GuidedAddState, options: list[tuple[str, str]]) -> GuidedAddState:
    state.ticker_suggestions = options
    state.ticker_page = 0
    return state


def apply_ticker(state: GuidedAddState, ticker: str) -> tuple[GuidedAddState, Optional[str]]:
    cleaned = ticker.strip().upper()
    if not cleaned:
        return state, "Ticker cannot be empty."
    state.draft = state.draft.model_copy(update={"ticker": cleaned})
    state.step_index += 1
    state.awaiting_text = None
    return state, None


def apply_quantity(
    state: GuidedAddState, raw: Optional[str], *, skip: bool = False
) -> tuple[GuidedAddState, Optional[str]]:
    if skip:
        state.draft = state.draft.model_copy(update={"quantity": None})
        state.step_index += 1
        state.awaiting_text = None
        return state, None
    try:
        qty = int(parse_number(raw or ""))
        if qty <= 0:
            return state, "Quantity must be a positive whole number."
    except (ValueError, TypeError):
        return state, "Invalid quantity. Enter a whole number, e.g. 10"
    state.draft = state.draft.model_copy(update={"quantity": qty})
    state.step_index += 1
    state.awaiting_text = None
    return state, None


def apply_currency(state: GuidedAddState, currency: str) -> tuple[GuidedAddState, Optional[str]]:
    try:
        state.draft = state.draft.model_copy(update={"currency": currency.strip().upper()})
        state.draft.refresh_missing_fields()
    except ValueError as exc:
        return state, str(exc)
    state.step_index += 1
    state.awaiting_text = None
    return state, None


def apply_value(state: GuidedAddState, raw: str) -> tuple[GuidedAddState, Optional[str]]:
    try:
        amount = parse_number(raw)
        if amount <= 0:
            return state, "Value must be greater than zero."
    except (ValueError, TypeError):
        return state, "Invalid amount. Example: 1850 or 1.41"
    state.draft = state.draft.model_copy(update={"value": amount})
    state.step_index += 1
    state.awaiting_text = None
    return state, None


def request_text_input(state: GuidedAddState, field_name: str) -> GuidedAddState:
    state.awaiting_text = field_name
    return state


def apply_text_input(state: GuidedAddState, text: str) -> tuple[GuidedAddState, Optional[str]]:
    waiting_for = state.awaiting_text
    if not waiting_for:
        return state, None

    if waiting_for == "portfolio":
        return apply_portfolio(state, text)
    if waiting_for == "date":
        return apply_date(state, text)
    if waiting_for == "ticker":
        return apply_ticker(state, text)
    if waiting_for == "quantity":
        return apply_quantity(state, text)
    if waiting_for == "value":
        return apply_value(state, text)
    return state, f"Unknown field: {waiting_for}"


def progress_summary(state: GuidedAddState) -> str:
    d = state.draft
    parts = []
    if d.action:
        parts.append(f"Type: *{d.action}*")
    if d.portfolio:
        parts.append(f"Portfolio: {d.portfolio}")
    if d.date:
        parts.append(f"Date: {d.date}")
    if d.ticker:
        parts.append(f"Ticker: {d.ticker}")
    if d.quantity is not None:
        parts.append(f"Qty: {d.quantity}")
    if d.currency:
        parts.append(f"Currency: {d.currency}")
    if d.value is not None:
        parts.append(f"Value: {d.value}")
    return " → ".join(parts) if parts else ""
