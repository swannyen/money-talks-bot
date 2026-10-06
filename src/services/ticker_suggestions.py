"""Suggest tickers from holdings and recent transactions (for /addsupport DIVIDEND)."""

from __future__ import annotations

import logging

import pandas as pd
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from src.services.database import TransactionDatabase
from src.services.holdings import load_holdings

logger = logging.getLogger(__name__)

MAX_TICKER_SUGGESTIONS = 60

RECENT_TICKERS_QUERY = text("""
    SELECT DISTINCT ON (ticker)
        ticker,
        asset_name
    FROM transactions
    WHERE portfolio = :portfolio
      AND ticker IS NOT NULL
      AND ticker <> ''
    ORDER BY ticker, id DESC
    LIMIT :limit
""")


def _label(ticker: str, asset_name: str | None) -> str:
    if asset_name and str(asset_name).strip():
        name = str(asset_name).strip()
        if len(name) > 22:
            name = name[:20] + "…"
        return f"{ticker} · {name}"
    return ticker


def load_ticker_suggestions(
    db: TransactionDatabase,
    portfolio: str,
    *,
    max_items: int = MAX_TICKER_SUGGESTIONS,
) -> list[tuple[str, str]]:
    """
    Return (ticker, button_label) pairs for the selected portfolio.

    Prefers open holdings, then fills from recent distinct tickers in that portfolio.
    """
    portfolio = portfolio.strip()
    seen: set[str] = set()
    results: list[tuple[str, str]] = []

    try:
        holdings = load_holdings(db)
        if not holdings.empty:
            subset = holdings[holdings["portfolio"] == portfolio]
            for _, row in subset.iterrows():
                ticker = str(row["ticker"]).strip().upper()
                if not ticker or ticker in seen:
                    continue
                seen.add(ticker)
                results.append((ticker, _label(ticker, row.get("asset_name"))))
                if len(results) >= max_items:
                    return results
    except SQLAlchemyError:
        logger.exception("Failed to load holdings for ticker suggestions")

    try:
        with db.engine.connect() as conn:
            recent = pd.read_sql(
                RECENT_TICKERS_QUERY,
                conn,
                params={"portfolio": portfolio, "limit": max_items * 2},
            )
        for _, row in recent.iterrows():
            ticker = str(row["ticker"]).strip().upper()
            if not ticker or ticker in seen:
                continue
            seen.add(ticker)
            asset_name = row.get("asset_name")
            results.append(
                (
                    ticker,
                    _label(ticker, str(asset_name) if pd.notna(asset_name) else None),
                )
            )
            if len(results) >= max_items:
                break
    except SQLAlchemyError:
        logger.exception("Failed to load recent tickers for suggestions")

    return results
