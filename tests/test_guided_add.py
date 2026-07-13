from src.guided_add import (
    GuidedAddState,
    apply_action,
    apply_currency,
    apply_date,
    apply_portfolio,
    apply_quantity,
    apply_text_input,
    apply_ticker,
    apply_value,
    change_ticker_page,
    parse_date_input,
    request_text_input,
    ticker_button_rows,
    ticker_page_count,
    uses_ticker_suggestions,
)


def _state_with_action(action: str) -> GuidedAddState:
    state = GuidedAddState()
    state, _ = apply_action(state, action)
    return state


def test_guided_buy_flow_to_complete():
    state = _state_with_action("BUY")
    assert state.current_step() == "portfolio"

    state, err = apply_portfolio(state, "Tiger")
    assert err is None
    state, err = apply_date(state, "today")
    assert err is None
    state, err = apply_ticker(state, "AAPL")
    assert err is None
    state, err = apply_quantity(state, "10")
    assert err is None
    state, err = apply_currency(state, "USD")
    assert err is None
    state, err = apply_value(state, "1850")
    assert err is None

    assert state.is_complete()
    assert state.draft.action == "BUY"
    assert state.draft.portfolio == "Tiger"
    assert state.draft.ticker == "AAPL"
    assert state.draft.quantity == 10
    assert state.draft.value == 1850.0
    assert state.draft.is_ready_for_confirmation()


def test_guided_sell_flow():
    state = _state_with_action("SELL")
    for fn, arg in [
        (apply_portfolio, "Tiger"),
        (apply_date, "2026-06-04"),
        (apply_ticker, "AAPL"),
        (apply_quantity, "5"),
        (apply_currency, "USD"),
        (apply_value, "920"),
    ]:
        state, err = fn(state, arg)
        assert err is None
    assert state.draft.action == "SELL"
    assert state.is_complete()


def test_guided_dividend_skip_quantity():
    state = _state_with_action("DIVIDEND")
    state, _ = apply_portfolio(state, "Tiger")
    state, _ = apply_date(state, "2026-06-01")
    state, _ = apply_ticker(state, "V")
    state, _ = apply_quantity(state, None, skip=True)
    assert state.current_step() == "currency"
    state, _ = apply_currency(state, "USD")
    state, _ = apply_value(state, "1.41")
    assert state.is_complete()
    assert state.draft.quantity is None
    assert state.draft.value == 1.41


def test_guided_fee_skips_quantity_step():
    state = _state_with_action("FEE")
    state, _ = apply_portfolio(state, "Tiger")
    state, _ = apply_date(state, "2026-06-01")
    state, _ = apply_ticker(state, "V")
    assert state.current_step() == "currency"
    state, _ = apply_currency(state, "USD")
    state, _ = apply_value(state, "0.60")
    assert state.draft.action == "FEE"
    assert state.is_complete()


def test_guided_deposit_skips_ticker_sets_na():
    state = _state_with_action("DEPOSIT")
    assert state.draft.ticker == "NA"
    assert state.current_step() == "portfolio"
    state, _ = apply_portfolio(state, "Tiger")
    state, _ = apply_date(state, "today")
    assert state.current_step() == "currency"
    assert state.draft.ticker == "NA"
    state, _ = apply_currency(state, "USD")
    state, _ = apply_value(state, "5000")
    assert state.draft.ticker == "NA"
    assert state.is_complete()


def test_parse_date_today_and_formats():
    assert parse_date_input("today") == parse_date_input("TODAY")
    assert parse_date_input("2026-06-04") == "2026-06-04"
    assert parse_date_input("15/06/2026") == "2026-06-15"


def test_ticker_button_rows_with_holdings():
    options = [("AAPL", "AAPL · Apple"), ("V", "V · Visa")]
    rows = ticker_button_rows(suggestions=options)
    flat = [data for row in rows for _label, data in row]
    assert "ga:tick:0" in flat
    assert "ga:tick:1" in flat
    assert "ga:text:ticker" in flat
    assert "ga:tpg:next" not in flat


def test_ticker_button_rows_pagination():
    options = [(f"T{i}", f"T{i}") for i in range(8)]
    assert ticker_page_count(len(options)) == 2

    page0 = ticker_button_rows(suggestions=options, page=0)
    flat0 = [data for row in page0 for _label, data in row]
    assert "ga:tick:0" in flat0
    assert "ga:tick:5" in flat0
    assert "ga:tick:6" not in flat0
    assert "ga:tpg:next" in flat0
    assert "ga:tpg:prev" not in flat0

    page1 = ticker_button_rows(suggestions=options, page=1)
    flat1 = [data for row in page1 for _label, data in row]
    assert "ga:tick:6" in flat1
    assert "ga:tick:7" in flat1
    assert "ga:tpg:prev" in flat1
    assert "ga:tpg:next" not in flat1


def test_ticker_button_rows_without_suggestions_for_buy():
    options = [("AAPL", "AAPL · Apple"), ("V", "V · Visa")]
    rows = ticker_button_rows(suggestions=options, include_suggestions=False)
    flat = [data for row in rows for _label, data in row]
    assert "ga:tick:0" not in flat
    assert "ga:tpg:next" not in flat
    assert "ga:text:ticker" in flat


def test_uses_ticker_suggestions_only_for_dividend():
    assert uses_ticker_suggestions("DIVIDEND") is True
    assert uses_ticker_suggestions("BUY") is False
    assert uses_ticker_suggestions("SELL") is False
    assert uses_ticker_suggestions("FEE") is False


def test_change_ticker_page():
    state = GuidedAddState()
    state.ticker_suggestions = [(f"T{i}", f"T{i}") for i in range(8)]
    state.ticker_page = 0
    state = change_ticker_page(state, 1)
    assert state.ticker_page == 1
    state = change_ticker_page(state, 1)
    assert state.ticker_page == 1
    state = change_ticker_page(state, -1)
    assert state.ticker_page == 0


def test_text_input_waits_for_field():
    state = _state_with_action("BUY")
    state, _ = apply_portfolio(state, "Tiger")
    state = request_text_input(state, "ticker")
    assert state.awaiting_text == "ticker"
    state, err = apply_text_input(state, "MSFT")
    assert err is None
    assert state.draft.ticker == "MSFT"
    assert state.awaiting_text is None
