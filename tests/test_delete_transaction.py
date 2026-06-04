import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from src.handlers.delete_transaction import delete_transaction_by_id, parse_delete_id


def test_parse_delete_id():
    assert parse_delete_id("delete 432") == 432
    assert parse_delete_id("DELETE 99") == 99
    assert parse_delete_id("delete432") is None


def test_delete_transaction_by_id_not_found():
    update = MagicMock()
    update.effective_chat.id = 1
    update.effective_message.reply_text = AsyncMock()

    with patch("src.handlers.delete_transaction.database") as mock_db:
        mock_db.get_by_id.return_value = None
        asyncio.run(delete_transaction_by_id(update, 999))

    assert "999" in update.effective_message.reply_text.call_args[0][0]


def test_delete_transaction_by_id_success():
    update = MagicMock()
    update.effective_chat.id = 1
    update.effective_message.reply_text = AsyncMock()

    row = {
        "id": 432,
        "date": "2026-06-04",
        "portfolio": "Vickers",
        "action": "BUY",
        "ticker": "AAPL",
        "value": 1850.0,
        "currency": "USD",
    }

    with patch("src.handlers.delete_transaction.database") as mock_db:
        mock_db.get_by_id.return_value = row
        mock_db.delete_by_id.return_value = True
        with patch("src.handlers.delete_transaction.sessions") as mock_sessions:
            mock_sessions.for_chat.return_value.last_inserted_id = 432
            asyncio.run(delete_transaction_by_id(update, 432))

    mock_db.delete_by_id.assert_called_once_with(432)
    assert mock_sessions.for_chat.return_value.last_inserted_id is None
