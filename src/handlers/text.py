"""Confirmation and edit reply handlers."""

from telegram import Update
from telegram.ext import ContextTypes

from src.bot_state import database, sessions
from src.config import get_settings
from src.edit_commands import apply_edit
from src.handlers.auth import reject_unauthorized
from src.handlers.delete_transaction import delete_transaction_by_id, parse_delete_id
from src.handlers.drafts import (
    discard_active_draft_message,
    save_confirmed,
    send_active_draft,
)
from src.handlers.guided_add import handle_guided_text
from src.handlers.manual_entry import submit_manual_line
from src.handlers.reminders import handle_reminder_text
from src.messages import edit_portfolio_hint, unknown_edit_format_hint
from src.services.draft_enrichment import enrich_draft


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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

    if await handle_reminder_text(update, text, context):
        return

    if await handle_guided_text(update, text):
        return

    guided = sessions.for_chat(chat_id).guided_add
    if guided is not None and guided.awaiting_text is None:
        handled = await _dispatch_text_command(update, lower, text, active)
        if handled:
            return
        await update.effective_message.reply_text(
            "Use the buttons from /addsupport, or send /addsupport to start over."
        )
        return

    handled = await _dispatch_text_command(update, lower, text, active)
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
        "Send a screenshot (photo), CSV/Excel, /addsupport, /add …, or /help."
    )


async def _dispatch_text_command(update, lower: str, text: str, active) -> bool:
    if lower == "reject":
        await discard_active_draft_message(update)
        return True

    if lower in {"confirm", "yes"}:
        if not active:
            await update.effective_message.reply_text(
                "Nothing to confirm. Upload a file, /addsupport, or /add …"
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

    if await submit_manual_line(update, text):
        return True

    return False


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
