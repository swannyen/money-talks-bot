"""Load a one-line manual transaction into the pending queue."""

from __future__ import annotations

from telegram import Update

from src.handlers.drafts import queue_draft, send_active_draft
from src.parsers.manual import parse_manual_line


async def submit_manual_line(update: Update, text: str, *, require: bool = False) -> bool:
    """Parse ``text`` as a manual entry. Returns True if handled (ok or error)."""
    chat_id = update.effective_chat.id
    manual, err = parse_manual_line(text, require=require)
    if err:
        await update.effective_message.reply_text(err)
        return True
    if not manual:
        return False
    queue_draft(chat_id, manual, make_active=True)
    await update.effective_message.reply_text("Manual entry loaded:")
    await send_active_draft(update)
    return True
