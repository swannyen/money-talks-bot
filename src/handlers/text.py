"""Confirmation and edit reply handlers."""

from telegram import Update
from telegram.ext import ContextTypes

from src.bot_state import database, sessions
from src.config import get_settings
from src.edit_commands import apply_edit
from src.handlers.auth import reject_unauthorized
from src.handlers.delete_transaction import delete_transaction_by_id, parse_delete_id
from src.handlers.drafts import queue_draft, save_confirmed, send_active_draft
from src.messages import edit_portfolio_hint, unknown_edit_format_hint
from src.parsers.manual import parse_manual_line
from src.services.draft_enrichment import enrich_draft


async def handle_text(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_unauthorized(update):
        return

    text = (update.effective_message.text or "").strip()
    lower = text.lower()
    chat_id = update.effective_chat.id
    session = sessions.for_chat(chat_id)
    active = session.get_active()

    delete_id = parse_delete_id(text)
    if delete_id is not None:
        await delete_transaction_by_id(update, delete_id)
        return

    handled = await _dispatch_text_command(update, lower, text, chat_id, active)
    if handled:
        return

    if active and active.draft.missing_fields:
        settings = get_settings()
        await update.effective_message.reply_text(
            f"Still missing: {', '.join(active.draft.missing_fields)}.\n"
            + edit_portfolio_hint(settings.portfolios),
            parse_mode="Markdown",
        )
        return

    await update.effective_message.reply_text(
        "Send a screenshot (photo), CSV/Excel file, use /help, or /add for manual format."
    )


async def _dispatch_text_command(update, lower: str, text: str, chat_id: int, active) -> bool:
    if lower == "reject":
        if active:
            session = sessions.for_chat(chat_id)
            session.remove_pending(active.id)
        await update.effective_message.reply_text("Discarded.")
        await send_active_draft(update)
        return True

    if lower in {"confirm", "yes"}:
        if not active:
            await update.effective_message.reply_text(
                "Nothing to confirm. Upload a file or use /add."
            )
            return True
        await save_confirmed(update, active.draft)
        return True

    if lower in {"confirm anyway", "save anyway"}:
        if not active:
            await update.effective_message.reply_text("Nothing to confirm.")
            return True
        await save_confirmed(update, active.draft, force=True)
        return True

    if lower.startswith("edit "):
        await _handle_edit(update, active, text)
        return True

    if await _try_manual_entry(update, text, chat_id):
        return True

    return False


async def _try_manual_entry(update, text: str, chat_id: int) -> bool:
    manual, err = parse_manual_line(text)
    if err:
        await update.effective_message.reply_text(err)
        return True
    if not manual:
        return False
    queue_draft(chat_id, manual, make_active=True)
    await update.effective_message.reply_text("Manual entry loaded:")
    await send_active_draft(update)
    return True


async def _handle_edit(update: Update, active, text: str) -> None:
    if not active:
        await update.effective_message.reply_text("No active draft to edit.")
        return
    updated, err = apply_edit(active.draft, text)
    if err:
        await update.effective_message.reply_text(f"Edit failed: {err}")
        return
    if updated is None:
        settings = get_settings()
        await update.effective_message.reply_text(
            unknown_edit_format_hint(settings.portfolios),
            parse_mode="Markdown",
        )
        return
    active.draft = enrich_draft(updated, database)
    await update.effective_message.reply_text("Updated draft:")
    await send_active_draft(update)
