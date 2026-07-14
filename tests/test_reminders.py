from datetime import datetime
from zoneinfo import ZoneInfo

from src.reminders import (
    ReminderPreference,
    next_weekday_at,
    parse_day_of_month,
    parse_time_input,
)


def test_default_preference_is_monthly_15th_8pm_sgt():
    pref = ReminderPreference.default_for(42)
    assert pref.enabled is True
    assert pref.frequency == "monthly"
    assert pref.day_of_month == 15
    assert pref.hour == 20
    assert pref.minute == 0
    assert pref.timezone == "Asia/Singapore"


def test_schedule_summary_monthly():
    pref = ReminderPreference.default_for(1)
    text = pref.schedule_summary()
    assert "On" in text
    assert "Monthly" in text
    assert "15th" in text
    assert "20:00" in text


def test_schedule_summary_weekly():
    pref = ReminderPreference(
        chat_id=1, frequency="weekly", weekday=2, hour=9, minute=30, timezone="Asia/Singapore"
    )
    assert "Weekly on Wed at 09:30" in pref.schedule_summary()


def test_parse_time_input():
    assert parse_time_input("20:00") == (20, 0)
    assert parse_time_input("8:05") == (8, 5)


def test_parse_time_input_rejects_bad_values():
    try:
        parse_time_input("25:00")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_parse_day_of_month():
    assert parse_day_of_month("15") == 15
    try:
        parse_day_of_month("31")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_next_weekday_at_skips_past_today():
    # Friday 2026-07-17 21:00 SGT — next Monday at 20:00
    zone = ZoneInfo("Asia/Singapore")
    now = datetime(2026, 7, 17, 21, 0, tzinfo=zone)
    pref = ReminderPreference(
        chat_id=1, frequency="weekly", weekday=0, hour=20, minute=0, timezone="Asia/Singapore"
    )
    nxt = next_weekday_at(pref, from_dt=now)
    assert nxt.weekday() == 0
    assert nxt.hour == 20
    assert nxt.date().isoformat() == "2026-07-20"


def test_preference_round_trip_dict():
    pref = ReminderPreference(
        chat_id=99,
        enabled=False,
        frequency="biweekly",
        hour=18,
        minute=15,
        weekday=4,
        day_of_month=7,
        timezone="Asia/Singapore",
    )
    restored = ReminderPreference.from_dict(pref.to_dict())
    assert restored == pref
