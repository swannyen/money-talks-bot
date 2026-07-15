"""Update reminder preferences — frequency, day, and time."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, time, timedelta
from typing import Literal, Optional
from zoneinfo import ZoneInfo

Frequency = Literal["daily", "weekly", "biweekly", "monthly"]

FREQUENCIES: tuple[Frequency, ...] = ("daily", "weekly", "biweekly", "monthly")
FREQUENCY_LABELS: dict[Frequency, str] = {
    "daily": "Daily",
    "weekly": "Weekly",
    "biweekly": "Every 2 weeks",
    "monthly": "Monthly",
}
WEEKDAY_LABELS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

DEFAULT_FREQUENCY: Frequency = "monthly"
DEFAULT_HOUR = 20
DEFAULT_MINUTE = 0
DEFAULT_DAY_OF_MONTH = 15
DEFAULT_WEEKDAY = 0  # Monday
DEFAULT_TIMEZONE = "Asia/Singapore"

REMINDER_MESSAGE = (
    "⏰ *Reminder:* time to update *Money Talks* with your latest transactions.\n\n"
    "Send a screenshot, CSV/Excel, /addsupport, or `/add …`."
)


@dataclass
class ReminderPreference:
    chat_id: int
    enabled: bool = True
    frequency: Frequency = DEFAULT_FREQUENCY
    hour: int = DEFAULT_HOUR
    minute: int = DEFAULT_MINUTE
    day_of_month: int = DEFAULT_DAY_OF_MONTH
    weekday: int = DEFAULT_WEEKDAY
    timezone: str = DEFAULT_TIMEZONE

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ReminderPreference":
        frequency = data.get("frequency", DEFAULT_FREQUENCY)
        if frequency not in FREQUENCIES:
            frequency = DEFAULT_FREQUENCY
        return cls(
            chat_id=int(data["chat_id"]),
            enabled=bool(data.get("enabled", True)),
            frequency=frequency,  # type: ignore[arg-type]
            hour=int(data.get("hour", DEFAULT_HOUR)),
            minute=int(data.get("minute", DEFAULT_MINUTE)),
            day_of_month=int(data.get("day_of_month", DEFAULT_DAY_OF_MONTH)),
            weekday=int(data.get("weekday", DEFAULT_WEEKDAY)),
            timezone=str(data.get("timezone") or DEFAULT_TIMEZONE),
        )

    @classmethod
    def default_for(cls, chat_id: int, *, timezone: str = DEFAULT_TIMEZONE) -> "ReminderPreference":
        return cls(chat_id=chat_id, timezone=timezone)

    def zone(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    def local_time(self) -> time:
        return time(hour=self.hour, minute=self.minute, tzinfo=self.zone())

    def schedule_summary(self) -> str:
        clock = f"{self.hour:02d}:{self.minute:02d}"
        tz_label = self.timezone.replace("_", " ")
        if self.frequency == "daily":
            detail = f"Daily at {clock} {tz_label}"
        elif self.frequency == "weekly":
            detail = f"Weekly on {WEEKDAY_LABELS[self.weekday]} at {clock} {tz_label}"
        elif self.frequency == "biweekly":
            detail = f"Every 2 weeks on {WEEKDAY_LABELS[self.weekday]} at {clock} {tz_label}"
        else:
            day = self.day_of_month
            detail = f"Monthly on the {day}{_ordinal_suffix(day)} at {clock} {tz_label}"
        status = "On" if self.enabled else "Off"
        return f"Status: *{status}*\nSchedule: {detail}"


def _ordinal_suffix(day: int) -> str:
    if 10 <= day % 100 <= 20:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")


def parse_time_input(raw: str) -> tuple[int, int]:
    """Parse HH:MM or H:MM. Raises ValueError."""
    text = raw.strip().lower().replace(".", ":")
    if "am" in text or "pm" in text:
        raise ValueError("Use 24-hour time, e.g. 20:00")
    parts = text.split(":")
    if len(parts) != 2:
        raise ValueError("Use HH:MM, e.g. 20:00")
    hour = int(parts[0])
    minute = int(parts[1])
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError("Hour must be 0–23 and minute 0–59.")
    return hour, minute


def parse_day_of_month(raw: str) -> int:
    day = int(raw.strip())
    if not 1 <= day <= 28:
        raise ValueError("Day must be between 1 and 28.")
    return day


def next_weekday_at(pref: ReminderPreference, *, from_dt: Optional[datetime] = None) -> datetime:
    """Next local datetime matching weekday + time (may be today if still upcoming)."""
    zone = pref.zone()
    now = from_dt.astimezone(zone) if from_dt else datetime.now(zone)
    candidate = now.replace(hour=pref.hour, minute=pref.minute, second=0, microsecond=0)
    days_ahead = (pref.weekday - candidate.weekday()) % 7
    if days_ahead == 0 and candidate <= now:
        days_ahead = 7
    return candidate + timedelta(days=days_ahead)


def next_biweekly_at(pref: ReminderPreference, *, from_dt: Optional[datetime] = None) -> datetime:
    return next_weekday_at(pref, from_dt=from_dt)


def job_name(chat_id: int) -> str:
    return f"reminder_{chat_id}"
