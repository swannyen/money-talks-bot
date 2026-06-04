import logging

import yfinance as yf

logger = logging.getLogger(__name__)


def get_ticker_metadata(ticker: str) -> dict[str, str | None]:
    try:
        info = yf.Ticker(ticker).info
        return {
            "asset_name": info.get("longName") or info.get("shortName"),
            "asset_class": info.get("quoteType"),
        }
    except (KeyError, TypeError, ValueError) as exc:
        logger.warning("yfinance lookup failed for %s: %s", ticker, exc.__class__.__name__)
        return {"asset_name": None, "asset_class": None}
