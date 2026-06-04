from src.parsers.vision import parse_vision_response


def test_dividend_table_mapping():
    raw = {
        "screen_type": "dividend_table",
        "date": "2026-06-01",
        "action": "DIVIDEND",
        "ticker": "V",
        "asset_name": "Visa",
        "quantity": 3,
        "currency": "USD",
        "cash_dividends": 2.01,
        "net_cash_value": 1.41,
        "fees_tax": 0.60,
        "confidence_score": 0.92,
        "missing_fields": ["portfolio"],
    }
    drafts = parse_vision_response(raw)
    assert len(drafts) == 1
    d = drafts[0]
    assert d.action == "DIVIDEND"
    assert d.ticker == "V"
    assert d.value == 1.41


def test_tiger_activity_feed_consolidates_dividend_and_tax():
    """Mobile screenshot: Cash Dividend +0.27 and Dividend Tax -0.08 for AAPL."""
    raw = {
        "screen_type": "activity_feed",
        "transactions": [
            {
                "line_type": "cash_dividend",
                "action": "DIVIDEND",
                "date": "2026-05-15",
                "time": "14:54:00",
                "ticker": "AAPL",
                "asset_name": "Apple",
                "amount": 0.27,
                "amount_sign": "+",
                "currency": "USD",
            },
            {
                "line_type": "dividend_tax",
                "action": "FEE",
                "date": "2026-05-15",
                "time": "15:14:06",
                "ticker": "AAPL",
                "asset_name": "Apple",
                "amount": 0.08,
                "amount_sign": "-",
                "currency": "USD",
            },
        ],
        "confidence_score": 0.9,
        "missing_fields": ["portfolio"],
        "notes": "Tiger mobile history 05/2026",
    }
    drafts = parse_vision_response(raw)

    assert len(drafts) == 1
    d = drafts[0]
    assert d.action == "DIVIDEND"
    assert d.ticker == "AAPL"
    assert d.asset_name == "Apple"
    assert d.date == "2026-05-15"
    assert d.currency == "USD"
    assert d.value == 0.19
    assert "0.27" in (d.notes or "")
    assert "0.08" in (d.notes or "")
    assert "portfolio" in d.missing_fields
