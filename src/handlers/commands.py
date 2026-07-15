"""Slash command handlers."""

import logging
import re

from sqlalchemy.exc import SQLAlchemyError
from telegram import Update
from telegram.ext import ContextTypes

from src.bot_state import database, sessions
from src.config import get_settings
from src.handlers.auth import reject_unauthorized
from src.handlers.delete_transaction import delete_transaction_by_id
from src.handlers.guided_add import start_guided_add
from src.handlers.manual_entry import submit_manual_line
from src.handlers.reminders import ensure_default_reminder
from src.messages import (
    build_add_usage_message,
    build_help_message,
    build_start_message,
)

logger = logging.getLogger(__name__)

_ADD_COMMAND_PREFIX = re.compile(r"^/add(?:@\w+)?\s*", re.IGNORECASE)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_unauthorized(update):
        return
    await ensure_default_reminder(update, context)
    settings = get_settings()
    await update.effective_message.reply_text(build_start_message(settings), parse_mode="Markdown")


async def help_command(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_unauthorized(update):
        return
    settings = get_settings()
    await update.effective_message.reply_text(
        build_help_message(settings),
        parse_mode="Markdown",
    )


async def recent_command(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_unauthorized(update):
        return
    try:
        df = database.get_recent(limit=10)
    except SQLAlchemyError:
        logger.exception("Failed to load recent transactions")
        await update.effective_message.reply_text(
            "Could not load transactions. Check DATABASE_URL."
        )
        return

    if df.empty:
        await update.effective_message.reply_text("No transactions found.")
        return

    lines = ["*Recent transactions:*", ""]
    for _, row in df.iterrows():
        lines.append(
            f"• `{row['id']}` {row['date']} | {row['portfolio']} | "
            f"{row['action']} {row['ticker']} | {row['value']} {row['currency']}"
        )
    await update.effective_message.reply_text(
        "\n".join(lines) + "\n\n_Delete: `/delete <id>`_", parse_mode="Markdown"
    )


async def undo_command(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_unauthorized(update):
        return
    session = sessions.for_chat(update.effective_chat.id)
    if session.last_inserted_id is None:
        await update.effective_message.reply_text("Nothing to undo.")
        return
    await delete_transaction_by_id(update, session.last_inserted_id)


async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_unauthorized(update):
        return
    if not context.args or len(context.args) != 1:
        await update.effective_message.reply_text(
            "Usage: `/delete 432`\n\nUse `/recent` to see ids.",
            parse_mode="Markdown",
        )
        return
    try:
        transaction_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text(
            "Transaction id must be a number, e.g. `/delete 432`.",
            parse_mode="Markdown",
        )
        return
    await delete_transaction_by_id(update, transaction_id)


async def add_command(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manual one-line entry: ``/add date … | portfolio … | …``."""
    if await reject_unauthorized(update):
        return

    raw = (update.effective_message.text or "").strip()
    payload = _ADD_COMMAND_PREFIX.sub("", raw, count=1).strip()
    if not payload:
        settings = get_settings()
        await update.effective_message.reply_text(
            build_add_usage_message(settings),
            parse_mode="Markdown",
        )
        return

    handled = await submit_manual_line(update, payload, require=True)
    if not handled:
        settings = get_settings()
        await update.effective_message.reply_text(
            build_add_usage_message(settings),
            parse_mode="Markdown",
        )


async def addsupport_command(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    """Guided button flow for adding a transaction."""
    if await reject_unauthorized(update):
        return
    await start_guided_add(update)
