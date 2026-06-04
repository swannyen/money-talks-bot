import pandas as pd

from src.services.holdings import (
    compute_holdings,
    fill_dividend_quantity_from_holdings,
    lookup_net_quantity,
)
from src.models import ExtractedTransaction


def _sample_transactions() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date": "2026-01-01",
                "portfolio": "Tiger",
                "ticker": "AAPL",
                "asset_name": "Apple",
                "asset_class": "EQUITY",
                "currency": "USD",
                "action": "BUY",
                "quantity": 10,
                "value_base": 1000.0,
            },
            {
                "date": "2026-02-01",
                "portfolio": "Tiger",
                "ticker": "AAPL",
                "asset_name": "Apple",
                "asset_class": "EQUITY",
                "currency": "USD",
                "action": "SELL",
                "quantity": 3,
                "value_base": 350.0,
            },
        ]
    )


def test_compute_holdings_net_quantity():
    holdings = compute_holdings(_sample_transactions())
    assert len(holdings) == 1
    assert lookup_net_quantity(holdings, portfolio="Tiger", ticker="AAPL", currency="USD") == 7


def test_fill_dividend_quantity_from_holdings():
    class FakeDB:
        @property
        def engine(self):
            raise AssertionError("should not hit DB in unit test")

    draft = ExtractedTransaction(
        date="2026-05-15",
        portfolio="Tiger",
        action="DIVIDEND",
        ticker="AAPL",
        currency="USD",
        value=0.19,
    )

    def fake_load(_db):
        return compute_holdings(_sample_transactions())

    import src.services.holdings as holdings_mod

    original = holdings_mod.load_holdings
    holdings_mod.load_holdings = fake_load
    try:
        enriched = fill_dividend_quantity_from_holdings(draft, FakeDB())  # type: ignore[arg-type]
    finally:
        holdings_mod.load_holdings = original

    assert enriched.quantity == 7
    assert "Quantity from holdings: 7" in (enriched.notes or "")
