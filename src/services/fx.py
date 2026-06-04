"""Foreign exchange conversion (Frankfurter API, same as Money Talks)."""

from __future__ import annotations

import logging

import requests

from src.config import get_settings

logger = logging.getLogger(__name__)

FRANKFURTER_URL = "https://api.frankfurter.app/latest"


def get_fx_rate(from_currency: str, base_currency: str) -> float:
    """
    Return how many units of ``from_currency`` equal 1 unit of ``base_currency``.

    Example: base SGD, from USD -> ~0.78 (1 SGD = 0.78 USD).
    """
    from_currency = from_currency.upper()
    base_currency = base_currency.upper()
    if from_currency == base_currency:
        return 1.0

    response = requests.get(
        FRANKFURTER_URL,
        params={"from": base_currency, "to": from_currency},
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()

    rates = data.get("rates") or {}
    rate = rates.get(from_currency)
    if rate is None:
        raise ValueError(f"No FX rate for {from_currency} vs {base_currency} (API: {data})")
    return float(rate)


def convert_value_to_base(amount: float, currency: str, base_currency: str | None = None) -> float:
    base = base_currency or get_settings().base_currency
    rate = get_fx_rate(currency, base)
    return amount / rate


def try_convert_value_to_base(
    amount: float, currency: str, base_currency: str | None = None
) -> float | None:
    """Convert to base currency; return None if the FX API is unavailable."""
    try:
        return convert_value_to_base(amount, currency, base_currency)
    except (ValueError, requests.RequestException) as exc:
        logger.warning("FX conversion failed for %s->%s: %s", currency, base_currency, exc)
        return None
