from src.models import ExtractedTransaction, PendingTransaction
from src.session import UserSession


def test_add_pending_make_active():
    session = UserSession()
    draft = ExtractedTransaction(
        date="2026-06-01",
        portfolio="Tiger",
        action="BUY",
        ticker="AAPL",
        currency="USD",
        value=100.0,
    )
    first = PendingTransaction(chat_id=1, draft=draft)
    second = PendingTransaction(chat_id=1, draft=draft)

    session.add_pending(first)
    session.add_pending(second, make_active=True)

    assert session.active_pending_id == second.id
    assert session.pending[0].id == second.id
