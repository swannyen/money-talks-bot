from src.parsers.manual import parse_manual_fields, parse_manual_line


def test_parse_manual_pipe_format():
    text = (
        "date 2026-06-04 | portfolio Vickers | action BUY | ticker AAPL | "
        "currency USD | quantity 10 | value 1850"
    )
    draft, err = parse_manual_line(text)
    assert err is None
    assert draft is not None
    assert draft.date == "2026-06-04"
    assert draft.portfolio == "Vickers"
    assert draft.action == "BUY"
    assert draft.ticker == "AAPL"
    assert draft.currency == "USD"
    assert draft.quantity == 10
    assert draft.value == 1850.0
    assert draft.is_ready_for_confirmation()


def test_parse_manual_colon_format():
    fields = parse_manual_fields(
        "date: 2026-06-04 | portfolio: Vickers | action: BUY | ticker: AAPL | "
        "currency: USD | quantity: 10 | value: 1850"
    )
    assert fields["portfolio"] == "Vickers"
    assert fields["value"] == "1850"


def test_parse_manual_without_pipes():
    text = (
        "date 2026-06-04 portfolio Vickers action BUY ticker AAPL "
        "currency USD quantity 10 value 1850"
    )
    draft, err = parse_manual_line(text)
    assert err is None
    assert draft is not None
    assert draft.portfolio == "Vickers"
