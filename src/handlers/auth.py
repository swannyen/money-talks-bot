"""Authorization helpers."""

import logging

from telegram import Update

from src.config import get_settings

logger = logging.getLogger(__name__)


def is_allowed(user_id: int | None) -> bool:
    if user_id is None:
        return False
    return user_id in get_settings().allowed_telegram_user_ids


async def reject_unauthorized(update: Update) -> bool:
    user = update.effective_user
    if user and is_allowed(user.id):
        return False
    if update.effective_message:
        await update.effective_message.reply_text("Unauthorized.")
    logger.warning("Rejected unauthorized user_id=%s", getattr(user, "id", None))
    return True
