"""Guided /addsupport conversation with inline buttons."""

from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from src.bot_state import database, sessions
from src.config import get_settings
from src.guided_add import (
    GuidedAddState,
    apply_action,
    apply_currency,
    apply_date,
    apply_portfolio,
    apply_quantity,
    apply_text_input,
    apply_ticker,
    build_step_message,
    buttons_for_step,
    change_ticker_page,
    request_text_input,
    set_ticker_suggestions,
    text_prompt_for_field,
    uses_ticker_suggestions,
)
from src.handlers.auth import reject_unauthorized
from src.handlers.drafts import (
    discard_active_draft,
    queue_draft,
    save_confirmed,
    send_active_draft,
    send_active_draft_for_review,
)
from src.services.ticker_suggestions import load_ticker_suggestions

logger = logging.getLogger(__name__)


def _markup(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(label, callback_data=data) for label, data in row] for row in rows]
    )


def _get_guided(chat_id: int) -> GuidedAddState | None:
    return sessions.for_chat(chat_id).guided_add


def _set_guided(chat_id: int, state: GuidedAddState | None) -> None:
    sessions.for_chat(chat_id).guided_add = state


def _ensure_ticker_suggestions(state: GuidedAddState) -> GuidedAddState:
    if (
        uses_ticker_suggestions(state.action)
        and state.draft.portfolio
        and not state.ticker_suggestions
    ):
        suggestions = load_ticker_suggestions(database, state.draft.portfolio)
        state = set_ticker_suggestions(state, suggestions)
    return state


def _step_keyboard(state: GuidedAddState) -> InlineKeyboardMarkup:
    settings = get_settings()
    step = state.current_step()
    return _markup(
        buttons_for_step(
            step,
            portfolios=settings.portfolios,
            currencies=settings.currencies,
            action=state.action,
            ticker_suggestions=state.ticker_suggestions,
            ticker_page=state.ticker_page,
        )
    )


async def _reply_step(update: Update, state: GuidedAddState) -> None:
    await update.effective_message.reply_text(
        build_step_message(state),
        parse_mode="Markdown",
        reply_markup=_step_keyboard(state),
    )


async def _edit_step(update: Update, state: GuidedAddState) -> None:
    query = update.callback_query
    if query is None or query.message is None:
        return
    await query.message.edit_text(
        build_step_message(state),
        parse_mode="Markdown",
        reply_markup=_step_keyboard(state),
    )


async def start_guided_add(update: Update) -> None:
    """Begin the guided add flow."""
    chat_id = update.effective_chat.id
    _set_guided(chat_id, GuidedAddState())
    await _send_step(update, chat_id)


async def _send_step(update: Update, chat_id: int) -> None:
    state = _get_guided(chat_id)
    if state is None:
        return

    if state.is_complete():
        draft = state.draft.model_copy()
        draft.refresh_missing_fields()
        _set_guided(chat_id, None)
        queue_draft(chat_id, draft, make_active=True)
        await send_active_draft_for_review(update)
        return

    if state.current_step() == "ticker" and state.action == "DIVIDEND":
        state = _ensure_ticker_suggestions(state)
        _set_guided(chat_id, state)

    await _reply_step(update, state)


async def _handle_save_callback(update: Update, chat_id: int, data: str) -> bool:
    query = update.callback_query
    if query is None:
        return False
    if data == "ga:save:confirm":
        active = sessions.for_chat(chat_id).get_active()
        if active is None:
            await query.message.reply_text("Nothing to confirm.")
        else:
            await save_confirmed(update, active.draft)
        return True
    if data == "ga:save:reject":
        discard_active_draft(chat_id)
        await query.message.reply_text("Discarded.")
        await send_active_draft(update)
        return True
    return False


async def _handle_ticker_page_callback(
    update: Update, chat_id: int, state: GuidedAddState, data: str
) -> bool:
    if data not in {"ga:tpg:prev", "ga:tpg:next"}:
        return False
    if state.action != "DIVIDEND" or state.current_step() != "ticker":
        return True
    delta = -1 if data == "ga:tpg:prev" else 1
    state = change_ticker_page(state, delta)
    _set_guided(chat_id, state)
    await _edit_step(update, state)
    return True


def _apply_callback_data(
    state: GuidedAddState, data: str, portfolios: list[str]
) -> tuple[GuidedAddState, str | None, str | None] | None:
    """Return updated state, optional error, or text-field name. None if unrecognized."""
    err: str | None = None
    text_field: str | None = None

    if data.startswith("ga:act:"):
        state, err = apply_action(state, data.removeprefix("ga:act:"))
    elif data.startswith("ga:pf:"):
        index = int(data.removeprefix("ga:pf:"))
        if index < 0 or index >= len(portfolios):
            err = "Invalid portfolio."
        else:
            state, err = apply_portfolio(state, portfolios[index])
    elif data == "ga:dt:today":
        state, err = apply_date(state, "today")
    elif data == "ga:dt:yesterday":
        state, err = apply_date(state, "yesterday")
    elif data.startswith("ga:ccy:"):
        state, err = apply_currency(state, data.removeprefix("ga:ccy:"))
    elif data == "ga:qty:skip":
        state, err = apply_quantity(state, None, skip=True)
    elif data.startswith("ga:tick:"):
        index = int(data.removeprefix("ga:tick:"))
        if state.action != "DIVIDEND":
            err = "Type the ticker symbol instead."
        elif index < 0 or index >= len(state.ticker_suggestions):
            err = "Invalid ticker selection."
        else:
            ticker, _label = state.ticker_suggestions[index]
            state, err = apply_ticker(state, ticker)
    elif data.startswith("ga:text:"):
        field_name = data.removeprefix("ga:text:")
        state = request_text_input(state, field_name)
        text_field = field_name
    else:
        return None

    return state, err, text_field


async def handle_guided_callback(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_unauthorized(update):
        return

    query = update.callback_query
    if query is None or not query.data or not query.data.startswith("ga:"):
        return

    await query.answer()
    chat_id = update.effective_chat.id
    data = query.data

    if await _handle_save_callback(update, chat_id, data):
        return

    state = _get_guided(chat_id)
    if state is None:
        await query.edit_message_text("Session expired. Send /addsupport to start again.")
        return

    if data == "ga:cancel":
        _set_guided(chat_id, None)
        await query.edit_message_text("Cancelled.")
        return

    if await _handle_ticker_page_callback(update, chat_id, state, data):
        return

    settings = get_settings()
    applied = _apply_callback_data(state, data, settings.portfolios)
    if applied is None:
        return
    state, err, text_field = applied
    if text_field:
        _set_guided(chat_id, state)
        await query.edit_message_text(text_prompt_for_field(text_field))
        return

    _set_guided(chat_id, state)
    if err:
        await query.message.reply_text(err)
    await _send_step(update, chat_id)


async def handle_guided_text(update: Update, text: str) -> bool:
    """Consume text when guided flow awaits typed input. Returns True if handled."""
    chat_id = update.effective_chat.id
    state = _get_guided(chat_id)
    if state is None or not state.awaiting_text:
        return False

    state, err = apply_text_input(state, text)
    _set_guided(chat_id, state)

    if err:
        field = state.awaiting_text or "value"
        await update.effective_message.reply_text(f"{err}\n\n{text_prompt_for_field(field)}")
        return True

    await _send_step(update, chat_id)
    return True
