from __future__ import annotations

from typing import Optional

from src.guided_add import GuidedAddState
from src.models import PendingTransaction


class UserSession:
    """In-memory state per Telegram chat (single-process deployment)."""

    def __init__(self):
        self.pending: list[PendingTransaction] = []
        self.active_pending_id: Optional[str] = None
        self.last_inserted_id: Optional[int] = None
        self.guided_add: Optional[GuidedAddState] = None

    def add_pending(self, item: PendingTransaction, *, make_active: bool = False) -> None:
        if make_active:
            self.pending.insert(0, item)
            self.active_pending_id = item.id
            return
        self.pending.append(item)
        if self.active_pending_id is None:
            self.active_pending_id = item.id

    def get_active(self) -> Optional[PendingTransaction]:
        if not self.active_pending_id:
            return None
        for item in self.pending:
            if item.id == self.active_pending_id:
                return item
        return None

    def remove_pending(self, pending_id: str) -> None:
        self.pending = [p for p in self.pending if p.id != pending_id]
        if self.active_pending_id == pending_id:
            self.active_pending_id = self.pending[0].id if self.pending else None

    def advance_active(self) -> Optional[PendingTransaction]:
        active = self.get_active()
        if active:
            self.remove_pending(active.id)
        return self.get_active()


class SessionStore:
    def __init__(self):
        self._sessions: dict[int, UserSession] = {}

    def for_chat(self, chat_id: int) -> UserSession:
        if chat_id not in self._sessions:
            self._sessions[chat_id] = UserSession()
        return self._sessions[chat_id]
