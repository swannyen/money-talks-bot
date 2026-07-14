"""Schedule Telegram reminder jobs via PTB JobQueue."""

from __future__ import annotations

import logging
from datetime import timedelta

from telegram.error import TelegramError
from telegram.ext import ContextTypes, JobQueue

from src.reminders import (
    REMINDER_MESSAGE,
    ReminderPreference,
    job_name,
    next_biweekly_at,
)

logger = logging.getLogger(__name__)


def _ptb_weekday(python_weekday: int) -> int:
    """Convert Python weekday (Mon=0) to PTB/APScheduler CronTrigger (Sun=0)."""
    return (python_weekday + 1) % 7


async def send_reminder(context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = context.job.chat_id if context.job else None
    if chat_id is None and context.job and isinstance(context.job.data, dict):
        chat_id = context.job.data.get("chat_id")
    if chat_id is None:
        logger.warning("Reminder job missing chat_id")
        return
    try:
        await context.bot.send_message(
            chat_id=chat_id, text=REMINDER_MESSAGE, parse_mode="Markdown"
        )
    except TelegramError:
        logger.exception("Failed to send reminder to chat_id=%s", chat_id)


def cancel_reminder_jobs(job_queue: JobQueue, chat_id: int) -> None:
    name = job_name(chat_id)
    for job in job_queue.get_jobs_by_name(name):
        job.schedule_removal()


def schedule_reminder(job_queue: JobQueue, pref: ReminderPreference) -> None:
    """Replace any existing job for this chat with the current preference."""
    cancel_reminder_jobs(job_queue, pref.chat_id)
    if not pref.enabled:
        return

    name = job_name(pref.chat_id)
    when = pref.local_time()
    data = {"chat_id": pref.chat_id}

    if pref.frequency == "daily":
        job_queue.run_daily(
            send_reminder,
            time=when,
            chat_id=pref.chat_id,
            name=name,
            data=data,
        )
    elif pref.frequency == "weekly":
        job_queue.run_daily(
            send_reminder,
            time=when,
            days=(_ptb_weekday(pref.weekday),),
            chat_id=pref.chat_id,
            name=name,
            data=data,
        )
    elif pref.frequency == "monthly":
        job_queue.run_monthly(
            send_reminder,
            when=when,
            day=pref.day_of_month,
            chat_id=pref.chat_id,
            name=name,
            data=data,
        )
    elif pref.frequency == "biweekly":
        first = next_biweekly_at(pref)
        job_queue.run_repeating(
            send_reminder,
            interval=timedelta(weeks=2),
            first=first,
            chat_id=pref.chat_id,
            name=name,
            data=data,
        )
    else:
        logger.error("Unknown reminder frequency=%s chat_id=%s", pref.frequency, pref.chat_id)
        return

    logger.info(
        "Scheduled reminder chat_id=%s frequency=%s time=%02d:%02d tz=%s",
        pref.chat_id,
        pref.frequency,
        pref.hour,
        pref.minute,
        pref.timezone,
    )


def reschedule_all(job_queue: JobQueue, prefs: list[ReminderPreference]) -> None:
    for pref in prefs:
        try:
            schedule_reminder(job_queue, pref)
        except (TypeError, ValueError, AttributeError):
            logger.exception("Failed to schedule reminder for chat_id=%s", pref.chat_id)
