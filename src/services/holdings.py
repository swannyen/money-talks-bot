"""Open-position quantity from transactions (WAC, matches Money Talks holdings)."""

from __future__ import annotations

import logging
from typing import Optional

import pandas as pd
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from src.models import ExtractedTransaction
from src.services.database import TransactionDatabase

logger = logging.getLogger(__name__)

HOLDINGS_QUERY = text("""
    SELECT
        date,
        portfolio,
        ticker,
        asset_name,
        asset_class,
        currency,
        action,
        quantity,
        value_base
    FROM transactions
    ORDER BY portfolio, ticker, currency, date, id
""")


def _prepare_transactions(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    prepared = df.copy()
    prepared["action"] = prepared["action"].str.upper().str.strip()
    prepared["ticker"] = prepared["ticker"].str.strip()
    prepared["currency"] = prepared["currency"].str.upper().str.strip()
    prepared["portfolio"] = prepared["portfolio"].str.strip()
    prepared["date"] = pd.to_datetime(prepared["date"], errors="coerce")
    prepared["quantity"] = pd.to_numeric(prepared["quantity"], errors="coerce")
    prepared["value_base"] = pd.to_numeric(prepared["value_base"], errors="coerce")
    return prepared.sort_values(["portfolio", "ticker", "currency", "date"]).reset_index(drop=True)


def _net_shares_from_group(group: pd.DataFrame) -> float:
    shares = 0.0
    for _, row in group.iterrows():
        action = row["action"]
        qty = row["quantity"]
        val_base = row["value_base"]
        if pd.isna(qty) or pd.isna(val_base):
            continue
        qty = float(qty)
        if action == "BUY":
            shares += qty
        elif action == "SELL":
            shares -= qty
    return shares


def compute_holdings(transactions: pd.DataFrame) -> pd.DataFrame:
    """Return open positions with Net Quantity (BUY/SELL WAC, same as Money Talks)."""
    df = _prepare_transactions(transactions)
    if df.empty:
        return pd.DataFrame(
            columns=["portfolio", "ticker", "asset_name", "asset_class", "currency", "net_quantity"]
        )

    group_cols = ["portfolio", "ticker", "asset_name", "asset_class", "currency"]
    rows: list[dict] = []

    for key, group in df.groupby(group_cols, sort=False):
        portfolio, ticker, asset_name, asset_class, currency = key
        shares = _net_shares_from_group(group)

        if shares > 1e-12:
            rows.append(
                {
                    "portfolio": portfolio,
                    "ticker": ticker,
                    "asset_name": asset_name,
                    "asset_class": asset_class,
                    "currency": currency,
                    "net_quantity": int(shares) if shares == int(shares) else shares,
                }
            )

    return pd.DataFrame(rows)


def lookup_net_quantity(
    holdings: pd.DataFrame,
    *,
    portfolio: str,
    ticker: str,
    currency: Optional[str] = None,
) -> Optional[float]:
    if holdings.empty:
        return None
    subset = holdings[
        (holdings["portfolio"] == portfolio) & (holdings["ticker"].str.upper() == ticker.upper())
    ]
    if currency:
        subset = subset[subset["currency"] == currency.upper()]
    if subset.empty:
        return None
    if len(subset) > 1 and not currency:
        total = subset["net_quantity"].sum()
        return float(total)
    return float(subset.iloc[0]["net_quantity"])


def load_holdings(db: TransactionDatabase) -> pd.DataFrame:
    with db.engine.connect() as conn:
        transactions = pd.read_sql(HOLDINGS_QUERY, conn)
    return compute_holdings(transactions)


def fill_dividend_quantity_from_holdings(
    draft: ExtractedTransaction,
    db: TransactionDatabase,
) -> ExtractedTransaction:
    """For DIVIDEND rows, set quantity from open holdings when portfolio+ticker are known."""
    if draft.action != "DIVIDEND":
        return draft
    if not draft.portfolio or not draft.ticker:
        return draft

    try:
        holdings = load_holdings(db)
    except SQLAlchemyError:
        logger.exception("Failed to load holdings for dividend quantity")
        return draft

    net = lookup_net_quantity(
        holdings,
        portfolio=draft.portfolio,
        ticker=draft.ticker,
        currency=draft.currency,
    )
    if net is None or net <= 0:
        note = draft.notes or ""
        suffix = "No open holding found — set quantity manually if needed"
        if suffix not in note:
            draft = draft.model_copy(update={"notes": f"{note} | {suffix}".strip(" |")})
        return draft

    qty = int(net) if net == int(net) else int(round(net))
    note = draft.notes or ""
    suffix = f"Quantity from holdings: {qty}"
    if suffix not in note:
        note = f"{note} | {suffix}".strip(" |")

    return draft.model_copy(update={"quantity": qty, "notes": note or None})
