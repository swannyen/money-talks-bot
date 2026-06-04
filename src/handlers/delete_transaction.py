"""Delete a transaction row by database id."""

from __future__ import annotations

import logging
import re

from sqlalchemy.exc import SQLAlchemyError
from telegram import Update

from src.bot_state import database, sessions

logger = logging.getLogger(__name__)

DELETE_TEXT_PATTERN = re.compile(r"^delete\s+(\d+)\s*$", re.IGNORECASE)


def parse_delete_id(text: str) -> int | None:
    match = DELETE_TEXT_PATTERN.match(text.strip())
    if not match:
        return None
    return int(match.group(1))


def _format_row_summary(row: dict) -> str:
    return (
        f"`{row['id']}` {row['date']} | {row['portfolio']} | "
        f"{row['action']} {row['ticker']} | {row['value']} {row['currency']}"
    )


async def delete_transaction_by_id(update: Update, transaction_id: int) -> None:
    try:
        row = database.get_by_id(transaction_id)
    except SQLAlchemyError:
        logger.exception("Lookup failed for id=%s", transaction_id)
        await update.effective_message.reply_text("Could not reach the database.")
        return

    if row is None:
        await update.effective_message.reply_text(
            f"No transaction with id `{transaction_id}`.", parse_mode="Markdown"
        )
        return

    try:
        deleted = database.delete_by_id(transaction_id)
    except SQLAlchemyError:
        logger.exception("Delete failed for id=%s", transaction_id)
        await update.effective_message.reply_text("Delete failed. Check logs.")
        return

    if not deleted:
        await update.effective_message.reply_text(
            f"Transaction `{transaction_id}` was not found.", parse_mode="Markdown"
        )
        return

    session = sessions.for_chat(update.effective_chat.id)
    if session.last_inserted_id == transaction_id:
        session.last_inserted_id = None

    await update.effective_message.reply_text(
        "Deleted:\n" + _format_row_summary(row),
        parse_mode="Markdown",
    )
