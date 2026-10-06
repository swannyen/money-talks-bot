"""Keep DB from being paused due to inactivity.

While the bot is running, this job queries the database every few hours so there is always activity,
and messages the allowed users if the database stays unreachable.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING

from sqlalchemy.exc import SQLAlchemyError
from telegram.error import TelegramError
from telegram.ext import ContextTypes, JobQueue

if TYPE_CHECKING:
    from src.services.database import TransactionDatabase

logger = logging.getLogger(__name__)

JOB_NAME = "db-keepalive"
FIRST_PING_DELAY = timedelta(seconds=30)
ALERT_AFTER_FAILURES = 3

DOWN_MESSAGE = (
    "⚠️ Database keep-alive: {failures} failed attempts in a row, so the bot can't reach "
    "the database. If Supabase shows the project as paused, restore it from the Supabase "
    "dashboard."
)
RECOVERED_MESSAGE = "✅ Database keep-alive: the database is reachable again."


@dataclass
class KeepaliveState:
    db: TransactionDatabase
    alert_chat_ids: tuple[int, ...]
    consecutive_failures: int = 0
    alerted: bool = False


async def _notify(context: ContextTypes.DEFAULT_TYPE, chat_ids: Iterable[int], text: str) -> bool:
    """Send text to each chat; True if at least one message went out."""
    sent = False
    for chat_id in chat_ids:
        try:
            await context.bot.send_message(chat_id=chat_id, text=text)
            sent = True
        except TelegramError:
            logger.exception("Failed to send keep-alive notice to chat_id=%s", chat_id)
    return sent


async def ping_database(context: ContextTypes.DEFAULT_TYPE) -> None:
    state: KeepaliveState = context.job.data
    try:
        row_count = await asyncio.to_thread(state.db.ping)
    except (SQLAlchemyError, RuntimeError):
        state.consecutive_failures += 1
        logger.warning(
            "Database keep-alive failed (%s in a row)", state.consecutive_failures, exc_info=True
        )
        if state.consecutive_failures >= ALERT_AFTER_FAILURES and not state.alerted:
            message = DOWN_MESSAGE.format(failures=state.consecutive_failures)
            state.alerted = await _notify(context, state.alert_chat_ids, message)
        return

    logger.info("Database keep-alive ok (transactions rows=%s)", row_count)
    state.consecutive_failures = 0
    if state.alerted:
        await _notify(context, state.alert_chat_ids, RECOVERED_MESSAGE)
        state.alerted = False


def schedule_keepalive(
    job_queue: JobQueue,
    db: TransactionDatabase,
    *,
    interval_hours: float,
    alert_chat_ids: Iterable[int],
) -> None:
    """Replace any existing keep-alive job; interval_hours of 0 leaves it off."""
    for job in job_queue.get_jobs_by_name(JOB_NAME):
        job.schedule_removal()

    if interval_hours <= 0:
        logger.info("Database keep-alive is off (DB_KEEPALIVE_HOURS=0)")
        return

    job_queue.run_repeating(
        ping_database,
        interval=timedelta(hours=interval_hours),
        first=FIRST_PING_DELAY,
        name=JOB_NAME,
        data=KeepaliveState(db=db, alert_chat_ids=tuple(sorted(alert_chat_ids))),
    )
    logger.info("Database keep-alive scheduled every %s hour(s)", interval_hours)
