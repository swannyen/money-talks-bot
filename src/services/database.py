from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional
from urllib.parse import urlparse

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool

from src.config import get_settings
from src.models import ExtractedTransaction
from src.services.transaction_builder import enrich_draft_for_insert

logger = logging.getLogger(__name__)


def _normalize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif url.startswith("postgresql://") and "+psycopg2" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    if "sslmode=" not in url:
        url += "&sslmode=require" if "?" in url else "?sslmode=require"
    return url


class TransactionDatabase:
    def __init__(self, database_url: Optional[str] = None):
        self._database_url = _normalize_database_url(database_url or get_settings().database_url)
        self._engine: Engine | None = None

    @property
    def engine(self) -> Engine:
        if self._engine is not None:
            return self._engine

        url = self._database_url
        host = urlparse(url).hostname or ""
        if host.startswith("db.") and host.endswith(".supabase.co"):
            raise RuntimeError(
                "DATABASE_URL uses Supabase direct host (db.*.supabase.co). "
                "Use the IPv4 pooler URL (port 6543) instead."
            )

        engine_kwargs: dict[str, Any] = {
            "pool_pre_ping": True,
            "connect_args": {"connect_timeout": 10},
        }
        if urlparse(url).port == 6543:
            engine_kwargs["poolclass"] = NullPool

        self._engine = create_engine(url, **engine_kwargs)
        return self._engine

    def ping(self) -> int:
        """Run a cheap query on the transactions table and return its row count.

        Used by the keep-alive job for the DB
        This reads a real table rather than just opening a connection.
        """
        with self.engine.connect() as conn:
            return int(conn.execute(text("SELECT COUNT(*) FROM transactions")).scalar_one())

    def get_recent(self, limit: int = 10) -> pd.DataFrame:
        query = text("""
            SELECT id, date, portfolio, ticker, currency, action, quantity, value
            FROM transactions
            ORDER BY id DESC
            LIMIT :limit
        """)
        with self.engine.connect() as conn:
            return pd.read_sql(query, conn, params={"limit": limit})

    def insert_transaction(self, row: dict[str, Any]) -> int:
        insert_sql = text("""
            INSERT INTO transactions (
                date, portfolio, ticker, asset_name, asset_class, currency,
                action, quantity, value, value_base, price_per_unit, year
            )
            VALUES (
                :date, :portfolio, :ticker, :asset_name, :asset_class, :currency,
                :action, :quantity, :value, :value_base, :price_per_unit, :year
            )
            RETURNING id
        """)
        with self.engine.begin() as conn:
            result = conn.execute(insert_sql, row)
            inserted_id = result.scalar_one()
        logger.info("Inserted transaction id=%s", inserted_id)
        return int(inserted_id)

    def get_by_id(self, transaction_id: int) -> dict[str, Any] | None:
        query = text("""
            SELECT id, date, portfolio, ticker, currency, action, quantity, value
            FROM transactions
            WHERE id = :id
        """)
        with self.engine.connect() as conn:
            row = conn.execute(query, {"id": transaction_id}).mappings().first()
        if row is None:
            return None
        return dict(row)

    def delete_by_id(self, transaction_id: int) -> bool:
        with self.engine.begin() as conn:
            result = conn.execute(
                text("DELETE FROM transactions WHERE id = :id"),
                {"id": transaction_id},
            )
        return result.rowcount > 0

    def find_similar(
        self,
        *,
        date: datetime,
        portfolio: str,
        ticker: str,
        action: str,
        currency: str,
        value: float,
        tolerance: float = 0.01,
    ) -> pd.DataFrame:
        query = text("""
            SELECT id, date, portfolio, ticker, currency, action, quantity, value
            FROM transactions
            WHERE portfolio = :portfolio
              AND ticker = :ticker
              AND action = :action
              AND currency = :currency
              AND date::date = :tx_date
              AND ABS(value - :value) <= :tolerance
            ORDER BY id DESC
            LIMIT 5
        """)
        with self.engine.connect() as conn:
            return pd.read_sql(
                query,
                conn,
                params={
                    "portfolio": portfolio,
                    "ticker": ticker,
                    "action": action,
                    "currency": currency,
                    "tx_date": date.date(),
                    "value": value,
                    "tolerance": tolerance,
                },
            )


def draft_to_db_row(draft: ExtractedTransaction) -> dict[str, Any]:
    """Map confirmed draft to DB insert parameters."""
    enriched = enrich_draft_for_insert(draft)
    dt = datetime.strptime(enriched.date[:10], "%Y-%m-%d")
    quantity = enriched.quantity if enriched.quantity is not None else 1

    return {
        "date": dt,
        "portfolio": enriched.portfolio,
        "ticker": enriched.ticker,
        "asset_name": enriched.asset_name,
        "asset_class": enriched.asset_class,
        "currency": enriched.currency,
        "action": enriched.action,
        "quantity": quantity,
        "value": enriched.value,
        "value_base": enriched.value_base,
        "price_per_unit": enriched.price_per_unit,
        "year": enriched.year,
    }
