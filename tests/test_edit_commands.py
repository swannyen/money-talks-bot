from src.edit_commands import apply_edit
from src.models import ExtractedTransaction


def test_apply_edit_value():
    draft = ExtractedTransaction(
        date="2026-06-01",
        portfolio="Tiger",
        action="BUY",
        ticker="AAPL",
        currency="USD",
        value=100.0,
    )
    updated, err = apply_edit(draft, "edit value 1850")
    assert err is None
    assert updated is not None
    assert updated.value == 1850.0


def test_apply_edit_action_sell_dividend_fee():
    base = ExtractedTransaction(
        date="2026-06-01",
        portfolio="Tiger",
        action="BUY",
        ticker="AAPL",
        currency="USD",
        value=100.0,
    )
    for action in ("SELL", "DIVIDEND", "FEE"):
        updated, err = apply_edit(base, f"edit action {action}")
        assert err is None
        assert updated is not None
        assert updated.action == action
