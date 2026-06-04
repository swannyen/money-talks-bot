"""LLM prompts for broker screenshot extraction."""

INVESTMENT_EXTRACTION_SYSTEM = """\
You extract investment transactions from broker app screenshots.

Two common layouts:

1) **Dividend table** (web/export): columns Date, Symbol, Cash Dividends, Net Cash Value, Currency.

2) **Activity / history feed** (mobile app, dark UI): stacked cards per event, e.g.:
   - "Cash Dividend" with +0.27, "AAPL Apple", "05/15/2026 14:54:00", "Balance: 3.01 USD"
   - "Dividend Tax" with -0.08 (orange), same ticker, later timestamp
   Parse EVERY visible transaction line into the transactions array.
   line_type: cash_dividend | dividend_tax | buy | sell | deposit | fee | other
   amount: positive magnitude; amount_sign: "+" or "-"
   ticker from "AAPL Apple" -> ticker AAPL, asset_name Apple

Do not guess portfolio. Always include "portfolio" in missing_fields.
Return ONLY valid JSON.
"""

INVESTMENT_EXTRACTION_USER = """\
Extract all transaction lines from this broker screenshot.

Allowed portfolios (only if visible): {portfolios}
Allowed currencies: {currencies}

**Activity feed** (mobile history): use screen_type "activity_feed" and fill transactions[].
**Dividend table**: use screen_type "dividend_table" with single-row fields OR transactions[].

JSON schema:
{{
  "screen_type": "activity_feed|dividend_table|buy|sell|unknown",
  "transactions": [
    {{
      "line_type": "cash_dividend|dividend_tax|buy|sell|deposit|fee|other",
      "action": "DIVIDEND|FEE|BUY|SELL|DEPOSIT|null",
      "date": "YYYY-MM-DD",
      "time": "HH:MM:SS or null",
      "ticker": "AAPL",
      "asset_name": "Apple",
      "amount": 0.27,
      "amount_sign": "+",
      "currency": "USD",
      "quantity": null
    }}
  ],
  "date": null,
  "portfolio": null,
  "action": null,
  "ticker": null,
  "cash_dividends": null,
  "net_cash_value": null,
  "fees_tax": null,
  "value": null,
  "confidence_score": 0.0-1.0,
  "missing_fields": ["portfolio"],
  "notes": "brief context"
}}

For Cash Dividend lines: line_type=cash_dividend, action=DIVIDEND.
For Dividend Tax lines: line_type=dividend_tax, action=FEE, amount=0.08, amount_sign="-".
Convert dates like 05/15/2026 to 2026-05-15.
"""
