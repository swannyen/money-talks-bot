import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.pool import StaticPool

from src.config import DEFAULT_DB_KEEPALIVE_HOURS, get_settings
from src.services.database import TransactionDatabase
from src.services.keepalive import (
    ALERT_AFTER_FAILURES,
    JOB_NAME,
    RECOVERED_MESSAGE,
    KeepaliveState,
    ping_database,
    schedule_keepalive,
)


def _db_down() -> OperationalError:
    return OperationalError("SELECT COUNT(*) FROM transactions", {}, Exception("server closed"))


def _context(state: KeepaliveState) -> MagicMock:
    context = MagicMock()
    context.job.data = state
    context.bot.send_message = AsyncMock()
    return context


def test_database_ping_counts_transactions():
    db = TransactionDatabase(database_url="postgresql://user:pass@localhost:5432/postgres")
    engine = create_engine("sqlite://", poolclass=StaticPool)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE transactions (id INTEGER)"))
        conn.execute(text("INSERT INTO transactions (id) VALUES (1), (2), (3)"))
    db._engine = engine  # pylint: disable=protected-access

    assert db.ping() == 3


def test_ping_success_sends_nothing():
    db = MagicMock()
    db.ping.return_value = 42
    state = KeepaliveState(db=db, alert_chat_ids=(1,))
    context = _context(state)

    asyncio.run(ping_database(context))

    db.ping.assert_called_once()
    assert state.consecutive_failures == 0
    context.bot.send_message.assert_not_called()


def test_alerts_once_after_repeated_failures():
    db = MagicMock()
    db.ping.side_effect = _db_down()
    state = KeepaliveState(db=db, alert_chat_ids=(1, 2))
    context = _context(state)

    for _ in range(ALERT_AFTER_FAILURES - 1):
        asyncio.run(ping_database(context))
    context.bot.send_message.assert_not_called()

    asyncio.run(ping_database(context))
    assert context.bot.send_message.await_count == 2
    assert {c.kwargs["chat_id"] for c in context.bot.send_message.await_args_list} == {1, 2}
    assert state.alerted is True

    asyncio.run(ping_database(context))
    assert context.bot.send_message.await_count == 2


def test_recovery_message_after_alert():
    db = MagicMock()
    db.ping.return_value = 5
    state = KeepaliveState(
        db=db, alert_chat_ids=(1,), consecutive_failures=ALERT_AFTER_FAILURES, alerted=True
    )
    context = _context(state)

    asyncio.run(ping_database(context))

    context.bot.send_message.assert_awaited_once_with(chat_id=1, text=RECOVERED_MESSAGE)
    assert state.consecutive_failures == 0
    assert state.alerted is False


def test_schedule_keepalive_registers_repeating_job():
    job_queue = MagicMock()
    job_queue.get_jobs_by_name.return_value = []
    db = MagicMock()

    schedule_keepalive(job_queue, db, interval_hours=4, alert_chat_ids={9, 3})

    job_queue.run_repeating.assert_called_once()
    kwargs = job_queue.run_repeating.call_args.kwargs
    assert kwargs["interval"] == timedelta(hours=4)
    assert kwargs["name"] == JOB_NAME
    assert kwargs["data"].db is db
    assert kwargs["data"].alert_chat_ids == (3, 9)


def test_schedule_keepalive_off_when_zero():
    old_job = MagicMock()
    job_queue = MagicMock()
    job_queue.get_jobs_by_name.return_value = [old_job]

    schedule_keepalive(job_queue, MagicMock(), interval_hours=0, alert_chat_ids={1})

    old_job.schedule_removal.assert_called_once()
    job_queue.run_repeating.assert_not_called()


def test_keepalive_hours_default(monkeypatch):
    monkeypatch.delenv("DB_KEEPALIVE_HOURS", raising=False)
    assert get_settings().db_keepalive_hours == DEFAULT_DB_KEEPALIVE_HOURS


def test_keepalive_hours_from_env(monkeypatch):
    monkeypatch.setenv("DB_KEEPALIVE_HOURS", "0.5")
    assert get_settings().db_keepalive_hours == 0.5


@pytest.mark.parametrize("raw", ["often", "-1", "inf"])
def test_keepalive_hours_rejects_bad_values(monkeypatch, raw):
    monkeypatch.setenv("DB_KEEPALIVE_HOURS", raw)
    with pytest.raises(RuntimeError, match="DB_KEEPALIVE_HOURS"):
        get_settings()
