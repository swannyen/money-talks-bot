"""Telegram bot entrypoint."""

from __future__ import annotations

import logging
import sys

from telegram import Update
from telegram.ext import Application

from src.config import get_settings
from src.handlers.register import register_handlers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def main() -> None:
    settings = get_settings()
    app = Application.builder().token(settings.telegram_bot_token).build()
    logger.info(
        "Starting bot allowed_user_ids=%s portfolios=%s",
        sorted(settings.allowed_telegram_user_ids),
        settings.portfolios,
    )
    register_handlers(app)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
