"""/remind — configure update reminder frequency and time."""

from __future__ import annotations

import logging
from dataclasses import replace

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from src.bot_state import get_reminder_store, sessions
from src.config import get_settings
from src.handlers.auth import reject_unauthorized
from src.reminders import (
    FREQUENCY_LABELS,
    FREQUENCIES,
    WEEKDAY_LABELS,
    Frequency,
    ReminderPreference,
    parse_day_of_month,
    parse_time_input,
)
from src.services.reminder_jobs import schedule_reminder

logger = logging.getLogger(__name__)

TIME_PRESETS = ((8, 0), (12, 0), (18, 0), (20, 0))
MONTH_DAY_PRESETS = (1, 7, 15, 28)


def _markup(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(label, callback_data=data) for label, data in row] for row in rows]
    )


def _main_keyboard(pref: ReminderPreference) -> InlineKeyboardMarkup:
    toggle = ("Turn off", "rm:off") if pref.enabled else ("Turn on", "rm:on")
    return _markup(
        [
            [("Frequency", "rm:menu:freq"), ("Time", "rm:menu:time")],
            [("Day", "rm:menu:day"), toggle],
            [("Done", "rm:done")],
        ]
    )


def _frequency_keyboard() -> InlineKeyboardMarkup:
    rows: list[list[tuple[str, str]]] = []
    row: list[tuple[str, str]] = []
    for freq in FREQUENCIES:
        row.append((FREQUENCY_LABELS[freq], f"rm:freq:{freq}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([("← Back", "rm:back")])
    return _markup(rows)


def _time_keyboard() -> InlineKeyboardMarkup:
    return _markup(
        [
            [(f"{h:02d}:{m:02d}", f"rm:time:{h:02d}:{m:02d}") for h, m in TIME_PRESETS[:2]],
            [(f"{h:02d}:{m:02d}", f"rm:time:{h:02d}:{m:02d}") for h, m in TIME_PRESETS[2:]],
            [("Type a time…", "rm:text:time")],
            [("← Back", "rm:back")],
        ]
    )


def _day_keyboard(pref: ReminderPreference) -> InlineKeyboardMarkup:
    if pref.frequency == "monthly":
        return _markup(
            [
                [(str(day), f"rm:dom:{day}") for day in MONTH_DAY_PRESETS[:2]],
                [(str(day), f"rm:dom:{day}") for day in MONTH_DAY_PRESETS[2:]],
                [("Type day (1–28)…", "rm:text:day")],
                [("← Back", "rm:back")],
            ]
        )
    return _markup(
        [
            [(WEEKDAY_LABELS[i], f"rm:wd:{i}") for i in range(0, 4)],
            [(WEEKDAY_LABELS[i], f"rm:wd:{i}") for i in range(4, 7)],
            [("← Back", "rm:back")],
        ]
    )


def _status_text(pref: ReminderPreference) -> str:
    if pref.frequency == "daily":
        note = "\n\n_Day does not apply to daily reminders._"
    elif pref.frequency == "monthly":
        note = "\n\n_Pick which day of the month (1–28)._"
    else:
        note = "\n\n_Pick which weekday reminders run on._"
    return (
        "⏰ *Update reminders*\n\n"
        f"{pref.schedule_summary()}\n\n"
        "Change frequency, day, or time below."
        f"{note}"
    )


def _ensure_pref(chat_id: int) -> ReminderPreference:
    settings = get_settings()
    store = get_reminder_store()
    pref = store.get_or_default(chat_id, timezone=settings.reminder_timezone)
    return store.save(pref)


def _persist_and_schedule(context: ContextTypes.DEFAULT_TYPE, pref: ReminderPreference) -> None:
    get_reminder_store().save(pref)
    if context.application.job_queue is None:
        logger.error("JobQueue unavailable — install python-telegram-bot[job-queue]")
        return
    schedule_reminder(context.application.job_queue, pref)


async def ensure_default_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Create and schedule the default monthly reminder the first time a chat appears."""
    chat_id = update.effective_chat.id
    if get_reminder_store().get(chat_id) is not None:
        return
    pref = _ensure_pref(chat_id)
    _persist_and_schedule(context, pref)


async def remind_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_unauthorized(update):
        return

    chat_id = update.effective_chat.id
    args = [a.lower() for a in (context.args or [])]

    if args and args[0] in {"off", "disable", "stop"}:
        pref = replace(_ensure_pref(chat_id), enabled=False)
        _persist_and_schedule(context, pref)
        await update.effective_message.reply_text(
            "Reminders turned *off*. Send `/remind` to change settings or turn them back on.",
            parse_mode="Markdown",
        )
        return

    if args and args[0] in {"on", "enable", "start"}:
        pref = replace(_ensure_pref(chat_id), enabled=True)
        _persist_and_schedule(context, pref)
        await update.effective_message.reply_text(
            f"Reminders turned *on*.\n\n{pref.schedule_summary()}",
            parse_mode="Markdown",
        )
        return

    pref = _ensure_pref(chat_id)
    sessions.for_chat(chat_id).reminder_awaiting = None
    await update.effective_message.reply_text(
        _status_text(pref),
        parse_mode="Markdown",
        reply_markup=_main_keyboard(pref),
    )


def _apply_reminder_callback(
    pref: ReminderPreference, data: str
) -> tuple[ReminderPreference | None, str | None]:
    """Return (updated pref or None if menu-only, optional awaiting field)."""
    if data == "rm:off":
        return replace(pref, enabled=False), None
    if data == "rm:on":
        return replace(pref, enabled=True), None
    if data.startswith("rm:freq:"):
        frequency = data.removeprefix("rm:freq:")
        if frequency not in FREQUENCIES:
            return None, None
        return replace(pref, frequency=frequency), None  # type: ignore[arg-type]
    if data.startswith("rm:time:"):
        try:
            hour, minute = parse_time_input(data.removeprefix("rm:time:"))
        except ValueError:
            return None, None
        return replace(pref, hour=hour, minute=minute), None
    if data.startswith("rm:dom:"):
        day = int(data.removeprefix("rm:dom:"))
        return replace(pref, day_of_month=day, frequency="monthly"), None
    if data.startswith("rm:wd:"):
        weekday = int(data.removeprefix("rm:wd:"))
        if not 0 <= weekday <= 6:
            return None, None
        freq: Frequency = pref.frequency if pref.frequency in {"weekly", "biweekly"} else "weekly"
        return replace(pref, weekday=weekday, frequency=freq), None
    if data == "rm:text:time":
        return pref, "time"
    if data == "rm:text:day":
        return pref, "day"
    return None, None


async def handle_reminder_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await reject_unauthorized(update):
        return

    query = update.callback_query
    if query is None or not query.data or not query.data.startswith("rm:"):
        return

    await query.answer()
    chat_id = update.effective_chat.id
    data = query.data
    pref = _ensure_pref(chat_id)
    sessions.for_chat(chat_id).reminder_awaiting = None

    if data == "rm:done":
        await query.edit_message_text(
            f"⏰ Reminder settings saved.\n\n{pref.schedule_summary()}",
            parse_mode="Markdown",
        )
        return

    if data == "rm:back":
        await query.edit_message_text(
            _status_text(pref),
            parse_mode="Markdown",
            reply_markup=_main_keyboard(pref),
        )
        return

    if data == "rm:menu:freq":
        await query.edit_message_text(
            "How often should I remind you?",
            reply_markup=_frequency_keyboard(),
        )
        return

    if data == "rm:menu:time":
        await query.edit_message_text(
            "What time? (24-hour, in your reminder timezone)",
            reply_markup=_time_keyboard(),
        )
        return

    if data == "rm:menu:day":
        if pref.frequency == "daily":
            await query.edit_message_text(
                "Daily reminders don't use a day setting.",
                reply_markup=_markup([[("← Back", "rm:back")]]),
            )
            return
        prompt = "Which day of the month?" if pref.frequency == "monthly" else "Which weekday?"
        await query.edit_message_text(prompt, reply_markup=_day_keyboard(pref))
        return

    updated, awaiting = _apply_reminder_callback(pref, data)
    if awaiting:
        sessions.for_chat(chat_id).reminder_awaiting = awaiting
        prompt = (
            "Type the time as `HH:MM` (e.g. `20:00`)."
            if awaiting == "time"
            else "Type the day of the month (1–28)."
        )
        await query.edit_message_text(prompt, parse_mode="Markdown")
        return

    if updated is None:
        return

    _persist_and_schedule(context, updated)
    await query.edit_message_text(
        _status_text(updated),
        parse_mode="Markdown",
        reply_markup=_main_keyboard(updated),
    )


async def handle_reminder_text(
    update: Update, text: str, context: ContextTypes.DEFAULT_TYPE
) -> bool:
    """Handle typed time/day while configuring reminders. Returns True if consumed."""
    chat_id = update.effective_chat.id
    awaiting = sessions.for_chat(chat_id).reminder_awaiting
    if not awaiting:
        return False

    pref = _ensure_pref(chat_id)
    try:
        if awaiting == "time":
            hour, minute = parse_time_input(text)
            pref = replace(pref, hour=hour, minute=minute)
        elif awaiting == "day":
            day = parse_day_of_month(text)
            pref = replace(pref, day_of_month=day, frequency="monthly")
        else:
            sessions.for_chat(chat_id).reminder_awaiting = None
            return False
    except ValueError as exc:
        await update.effective_message.reply_text(str(exc))
        return True

    sessions.for_chat(chat_id).reminder_awaiting = None
    _persist_and_schedule(context, pref)
    await update.effective_message.reply_text(
        _status_text(pref),
        parse_mode="Markdown",
        reply_markup=_main_keyboard(pref),
    )
    return True
