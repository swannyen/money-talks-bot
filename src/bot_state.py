"""Shared bot singletons (database + session store)."""

from src.config import get_settings
from src.services.database import TransactionDatabase
from src.services.reminder_store import ReminderStore
from src.session import SessionStore

sessions = SessionStore()
database = TransactionDatabase()


def get_reminder_store() -> ReminderStore:
    return ReminderStore(get_settings().reminder_store_path)
