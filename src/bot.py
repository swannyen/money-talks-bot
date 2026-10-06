"""Telegram bot entrypoint."""

from __future__ import annotations

import logging
import sys

from telegram import Update
from telegram.ext import Application

from src.bot_state import database, get_reminder_store
from src.config import get_settings
from src.handlers.register import register_handlers
from src.services.keepalive import schedule_keepalive
from src.services.reminder_jobs import reschedule_all

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


async def _post_init(app: Application) -> None:
    if app.job_queue is None:
        logger.error(
            "JobQueue is unavailable. Install: pip install 'python-telegram-bot[job-queue]'"
        )
        return
    prefs = get_reminder_store().list_all()
    reschedule_all(app.job_queue, prefs)
    logger.info("Loaded %s reminder preference(s)", len(prefs))

    settings = get_settings()
    schedule_keepalive(
        app.job_queue,
        database,
        interval_hours=settings.db_keepalive_hours,
        alert_chat_ids=settings.allowed_telegram_user_ids,
    )


def main() -> None:
    settings = get_settings()
    app = Application.builder().token(settings.telegram_bot_token).post_init(_post_init).build()
    logger.info(
        "Starting bot allowed_user_ids=%s portfolios=%s reminder_tz=%s",
        sorted(settings.allowed_telegram_user_ids),
        settings.portfolios,
        settings.reminder_timezone,
    )
    register_handlers(app)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
