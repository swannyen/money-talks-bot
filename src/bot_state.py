"""Shared bot singletons (database + session store)."""

from src.services.database import TransactionDatabase
from src.session import SessionStore

sessions = SessionStore()
database = TransactionDatabase()
