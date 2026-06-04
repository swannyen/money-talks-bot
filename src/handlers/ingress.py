"""File and photo upload handlers."""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from src.handlers.auth import reject_unauthorized
from src.handlers.drafts import queue_draft, send_active_draft
from src.parsers.spreadsheet import parse_spreadsheet_bytes
from src.parsers.vision import (
    VisionNotConfiguredError,
    VisionParserError,
    extract_transactions_from_image,
)

logger = logging.getLogger(__name__)


def mime_type_from_photo(photo_path: str | None) -> str:
    if photo_path and photo_path.lower().endswith(".png"):
        return "image/png"
    return "image/jpeg"


async def handle_document(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_unauthorized(update):
        return

    document = update.effective_message.document
    filename = document.file_name or "upload.csv"
    try:
        tg_file = await document.get_file()
        content = await tg_file.download_as_bytearray()
        drafts = parse_spreadsheet_bytes(bytes(content), filename)
    except ValueError as exc:
        await update.effective_message.reply_text(f"Could not parse file: {exc}")
        return
    except OSError:
        logger.exception("Document download failed")
        await update.effective_message.reply_text("Failed to download file.")
        return

    if not drafts:
        await update.effective_message.reply_text("No transaction rows found in file.")
        return

    chat_id = update.effective_chat.id
    for idx, draft in enumerate(drafts):
        queue_draft(chat_id, draft, row_index=idx)

    await update.effective_message.reply_text(
        f"Queued *{len(drafts)}* transaction(s). Review the first one:",
        parse_mode="Markdown",
    )
    await send_active_draft(update)


async def handle_photo(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_unauthorized(update):
        return

    photos = update.effective_message.photo
    if not photos:
        return

    largest = photos[-1]
    await update.effective_message.reply_text("Reading screenshot…")

    try:
        tg_file = await largest.get_file()
        image_bytes = bytes(await tg_file.download_as_bytearray())
        mime = mime_type_from_photo(tg_file.file_path)
        drafts = extract_transactions_from_image(image_bytes, mime_type=mime)
    except VisionNotConfiguredError as exc:
        await update.effective_message.reply_text(str(exc))
        return
    except VisionParserError as exc:
        await update.effective_message.reply_text(f"Could not read screenshot: {exc}")
        return
    except OSError:
        logger.exception("Photo download failed")
        await update.effective_message.reply_text(
            "Failed to download screenshot. Try again or use CSV export."
        )
        return

    chat_id = update.effective_chat.id
    for draft in drafts:
        queue_draft(chat_id, draft)

    await update.effective_message.reply_text(
        f"Screenshot parsed — *{len(drafts)}* transaction(s) queued. " "Review and confirm:",
        parse_mode="Markdown",
    )
    await send_active_draft(update)
