"""Slash command handlers."""

import logging

from sqlalchemy.exc import SQLAlchemyError
from telegram import Update
from telegram.ext import ContextTypes

from src.bot_state import database, sessions
from src.config import get_settings
from src.formatting import format_pending_list
from src.handlers.auth import reject_unauthorized
from src.handlers.delete_transaction import delete_transaction_by_id
from src.messages import build_add_message, build_help_message, build_start_message

logger = logging.getLogger(__name__)


async def start_command(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_unauthorized(update):
        return
    settings = get_settings()
    await update.effective_message.reply_text(
        build_start_message(settings), parse_mode="Markdown"
    )


async def help_command(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_unauthorized(update):
        return
    settings = get_settings()
    await update.effective_message.reply_text(
        build_help_message(settings),
        parse_mode="Markdown",
    )


async def pending_command(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_unauthorized(update):
        return
    chat_id = update.effective_chat.id
    session = sessions.for_chat(chat_id)
    await update.effective_message.reply_text(
        format_pending_list(session.pending),
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
    if await reject_unauthorized(update):
        return
    settings = get_settings()
    await update.effective_message.reply_text(
        build_add_message(settings), parse_mode="Markdown"
    )
