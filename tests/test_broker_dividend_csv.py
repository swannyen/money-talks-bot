from pathlib import Path

from src.parsers.spreadsheet import parse_spreadsheet_bytes

SAMPLE_CSV = Path(__file__).resolve().parent / "fixtures" / "tiger_dividend.csv"


def test_parse_tiger_sample_csv():
    content = SAMPLE_CSV.read_bytes()
    drafts = parse_spreadsheet_bytes(content, "sample.csv")

    assert len(drafts) == 1
    d = drafts[0]
    assert d.action == "DIVIDEND"
    assert d.date == "2026-06-01"
    assert d.ticker == "V"
    assert d.asset_name == "Visa"
    assert d.quantity == 3
    assert d.currency == "USD"
    assert d.value == 1.41
    assert d.portfolio is None
    assert "portfolio" in d.missing_fields
    assert "Broker dividend" in (d.notes or "")


def test_detect_format_from_headers_only():
    from src.parsers.broker_dividend import is_broker_dividend_export

    tiger_cols = [
        "Date",
        "Product",
        "Symbol",
        "Cash Dividends",
        "Net Cash Value",
        "Currency",
    ]
    assert is_broker_dividend_export(tiger_cols)

    money_talks_cols = ["Date", "Portfolio", "Ticker", "Action", "Value", "Currency"]
    assert not is_broker_dividend_export(money_talks_cols)
