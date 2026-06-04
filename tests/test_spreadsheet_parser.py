import io

import pandas as pd

from src.parsers.spreadsheet import parse_spreadsheet_bytes


def test_parse_csv_export():
    df = pd.DataFrame(
        [
            {
                "Date": "2026-06-01",
                "Portfolio": "Tiger",
                "Ticker": "AAPL",
                "Currency": "USD",
                "Action": "BUY",
                "Quantity": 10,
                "Value": 1850.0,
            }
        ]
    )
    buffer = io.BytesIO()
    df.to_csv(buffer, index=False)
    drafts = parse_spreadsheet_bytes(buffer.getvalue(), "transactions.csv")

    assert len(drafts) == 1
    d = drafts[0]
    assert d.date == "2026-06-01"
    assert d.portfolio == "Tiger"
    assert d.action == "BUY"
    assert d.ticker == "AAPL"
    assert d.currency == "USD"
    assert d.value == 1850.0
    assert d.is_ready_for_confirmation()


def test_missing_required_columns_raises():
    df = pd.DataFrame([{"Date": "2026-06-01", "Value": 100}])
    buffer = io.BytesIO()
    df.to_csv(buffer, index=False)
    try:
        parse_spreadsheet_bytes(buffer.getvalue(), "bad.csv")
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "portfolio" in str(exc).lower() or "action" in str(exc).lower()
