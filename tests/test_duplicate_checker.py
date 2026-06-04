from unittest.mock import MagicMock

import pandas as pd

from src.services.duplicate_checker import check_duplicates, format_duplicate_warning
from src.models import ExtractedTransaction


def test_duplicate_warning_message():
    draft = ExtractedTransaction(
        date="2026-06-01",
        portfolio="Tiger",
        action="BUY",
        ticker="AAPL",
        currency="USD",
        value=100.0,
    )
    mock_db = MagicMock()
    mock_db.find_similar.return_value = pd.DataFrame(
        [
            {
                "id": 42,
                "date": "2026-06-01",
                "action": "BUY",
                "ticker": "AAPL",
                "value": 100,
                "currency": "USD",
            }
        ]
    )
    result = check_duplicates(draft, mock_db)
    assert result.has_duplicates
    warning = format_duplicate_warning(result)
    assert "42" in warning
    assert "confirm anyway" in warning.lower()
