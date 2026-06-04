"""Pending transaction queue and save flow."""

import logging

from sqlalchemy.exc import SQLAlchemyError
from telegram import Update

from src.bot_state import database, sessions
from src.services.database import draft_to_db_row
from src.services.draft_enrichment import enrich_draft
from src.services.duplicate_checker import check_duplicates, format_duplicate_warning
from src.formatting import format_transaction_summary
from src.models import ExtractedTransaction, PendingTransaction

logger = logging.getLogger(__name__)


def queue_draft(
    chat_id: int,
    draft: ExtractedTransaction,
    row_index: int | None = None,
    *,
    make_active: bool = False,
) -> PendingTransaction:
    pending = PendingTransaction(chat_id=chat_id, draft=draft, row_index=row_index)
    sessions.for_chat(chat_id).add_pending(pending, make_active=make_active)
    return pending


async def send_active_draft(update: Update, *, duplicate_note: str = "") -> None:
    session = sessions.for_chat(update.effective_chat.id)
    active = session.get_active()
    if not active:
        await update.effective_message.reply_text("No pending transaction.")
        return
    active.draft = enrich_draft(active.draft, database)
    text = format_transaction_summary(active.draft)
    if duplicate_note:
        text = duplicate_note + "\n\n" + text
    await update.effective_message.reply_text(text, parse_mode="Markdown")


async def save_confirmed(
    update: Update, draft: ExtractedTransaction, *, force: bool = False
) -> None:
    draft = enrich_draft(draft, database)
    if not draft.is_ready_for_confirmation():
        await update.effective_message.reply_text(
            f"Missing fields: {', '.join(draft.missing_fields)}. "
            "Use `edit <field> <value>` or send corrected data."
        )
        return

    dup = check_duplicates(draft, database)
    if dup.has_duplicates and not force:
        context_note = format_duplicate_warning(dup)
        await update.effective_message.reply_text(context_note, parse_mode="Markdown")
        await send_active_draft(update)
        return

    try:
        row = draft_to_db_row(draft)
        inserted_id = database.insert_transaction(row)
    except (SQLAlchemyError, ValueError, TypeError):
        logger.exception("Insert failed")
        await update.effective_message.reply_text(
            "Save failed. Check logs and database connection."
        )
        return

    session = sessions.for_chat(update.effective_chat.id)
    session.last_inserted_id = inserted_id
    session.advance_active()
    await update.effective_message.reply_text(
        f"✅ Saved transaction id `{inserted_id}`.",
        parse_mode="Markdown",
    )
    if session.get_active():
        await update.effective_message.reply_text(
            f"Next pending ({len(session.pending)} left):",
        )
        await send_active_draft(update)
