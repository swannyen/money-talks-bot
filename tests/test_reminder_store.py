from pathlib import Path

from src.reminders import ReminderPreference
from src.services.reminder_store import ReminderStore


def test_reminder_store_save_and_get(tmp_path: Path):
    store = ReminderStore(tmp_path / "reminders.json")
    pref = ReminderPreference.default_for(123)
    store.save(pref)
    loaded = store.get(123)
    assert loaded is not None
    assert loaded.chat_id == 123
    assert loaded.frequency == "monthly"
    assert loaded.day_of_month == 15


def test_reminder_store_list_all(tmp_path: Path):
    store = ReminderStore(tmp_path / "reminders.json")
    store.save(ReminderPreference.default_for(1))
    store.save(ReminderPreference(chat_id=2, frequency="daily", enabled=False))
    prefs = store.list_all()
    assert {p.chat_id for p in prefs} == {1, 2}


def test_get_or_default_does_not_persist(tmp_path: Path):
    store = ReminderStore(tmp_path / "reminders.json")
    pref = store.get_or_default(55, timezone="Asia/Singapore")
    assert pref.chat_id == 55
    assert store.get(55) is None
