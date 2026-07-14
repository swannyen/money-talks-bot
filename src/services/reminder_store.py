"""Persist reminder preferences to a JSON file (survives bot restarts)."""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Optional

from src.reminders import ReminderPreference

logger = logging.getLogger(__name__)

_lock = threading.Lock()


class ReminderStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load_all(self) -> dict[str, dict]:
        if not self.path.exists():
            return {}
        try:
            with self.path.open(encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, dict):
                return data
        except (OSError, json.JSONDecodeError):
            logger.exception("Failed to load reminders from %s", self.path)
        return {}

    def _save_all(self, data: dict[str, dict]) -> None:
        tmp = self.path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, sort_keys=True)
        tmp.replace(self.path)

    def list_all(self) -> list[ReminderPreference]:
        with _lock:
            return [ReminderPreference.from_dict(raw) for raw in self._load_all().values()]

    def get(self, chat_id: int) -> Optional[ReminderPreference]:
        with _lock:
            raw = self._load_all().get(str(chat_id))
            return ReminderPreference.from_dict(raw) if raw else None

    def save(self, pref: ReminderPreference) -> ReminderPreference:
        with _lock:
            data = self._load_all()
            data[str(pref.chat_id)] = pref.to_dict()
            self._save_all(data)
        return pref

    def get_or_default(self, chat_id: int, *, timezone: str) -> ReminderPreference:
        existing = self.get(chat_id)
        if existing is not None:
            return existing
        return ReminderPreference.default_for(chat_id, timezone=timezone)
