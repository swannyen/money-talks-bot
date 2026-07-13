import pytest

from src.config import ACCEPTED_ACTIONS
from src.parsers.manual import parse_manual_fields, parse_manual_line


def test_parse_manual_pipe_format_buy():
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


@pytest.mark.parametrize(
    ("action", "ticker", "quantity", "value"),
    [
        ("SELL", "AAPL", 5, 920.0),
        ("DIVIDEND", "V", 3, 1.41),
        ("FEE", "V", None, 0.60),
    ],
)
def test_parse_manual_pipe_format_actions(action, ticker, quantity, value):
    qty_part = f"| quantity {quantity} " if quantity is not None else " "
    text = (
        f"date 2026-06-04 | portfolio Tiger | action {action} | ticker {ticker} "
        f"currency USD {qty_part}| value {value}"
    )
    draft, err = parse_manual_line(text)
    assert err is None
    assert draft is not None
    assert draft.action == action
    assert draft.ticker == ticker
    assert draft.quantity == quantity
    assert draft.value == value
    assert draft.is_ready_for_confirmation()


@pytest.mark.parametrize("action", ["SELL", "DIVIDEND", "FEE"])
def test_parse_manual_lowercase_action(action):
    text = (
        f"date 2026-06-04 | portfolio Tiger | action {action.lower()} | ticker V | "
        f"currency USD | value 1.41"
    )
    draft, err = parse_manual_line(text)
    assert err is None
    assert draft is not None
    assert draft.action == action


def test_parse_manual_colon_format_sell():
    fields = parse_manual_fields(
        "date: 2026-06-04 | portfolio: Tiger | action: SELL | ticker: AAPL | "
        "currency: USD | quantity: 5 | value: 920"
    )
    assert fields["action"] == "SELL"
    assert fields["value"] == "920"

    draft, err = parse_manual_line(
        "date: 2026-06-04 | portfolio: Tiger | action: SELL | ticker: AAPL | "
        "currency: USD | quantity: 5 | value: 920"
    )
    assert err is None
    assert draft is not None
    assert draft.action == "SELL"
    assert draft.is_ready_for_confirmation()


def test_parse_manual_without_pipes_dividend():
    text = (
        "date 2026-06-01 portfolio Tiger action DIVIDEND ticker V "
        "currency USD quantity 3 value 1.41"
    )
    draft, err = parse_manual_line(text)
    assert err is None
    assert draft is not None
    assert draft.action == "DIVIDEND"
    assert draft.value == 1.41


def test_parse_manual_value_with_commas_and_currency_symbol():
    text = (
        "date 2026-06-04 | portfolio Tiger | action BUY | ticker AAPL | "
        "currency USD | quantity 10 | value $1,850.50"
    )
    draft, err = parse_manual_line(text)
    assert err is None
    assert draft is not None
    assert draft.value == 1850.50


def test_parse_manual_action_alias_dividends():
    text = (
        "date 2026-06-01 | portfolio Tiger | action dividends | ticker V | "
        "currency USD | value 1.41"
    )
    draft, err = parse_manual_line(text)
    assert err is None
    assert draft is not None
    assert draft.action == "DIVIDEND"


def test_parse_manual_invalid_action_message():
    text = (
        "date 2026-06-04 | portfolio Tiger | action PURCHASE | ticker AAPL | "
        "currency USD | value 100"
    )
    draft, err = parse_manual_line(text)
    assert draft is None
    assert err is not None
    assert "Invalid action" in err
    assert "PURCHASE" in err
    for action in ACCEPTED_ACTIONS:
        assert action in err
