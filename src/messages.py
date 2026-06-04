"""Telegram bot copy — built from settings so examples match each user's `.env`."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.config import Settings


def portfolio_example(portfolios: list[str], index: int = 0) -> str:
    """Portfolio name for examples, or ``<Portfolio>`` when none are configured."""
    if portfolios and index < len(portfolios):
        return portfolios[index]
    return "<Portfolio>"


def _manual_entry_line(portfolios: list[str]) -> str:
    portfolio = portfolio_example(portfolios, 0)
    return (
        f"date 2026-06-04 | portfolio {portfolio} | action BUY | "
        f"ticker AAPL | currency USD | quantity 10 | value 1850"
    )


def _portfolio_edit_examples(portfolios: list[str]) -> str:
    if not portfolios:
        return "• `edit portfolio <Portfolio>`"
    lines = [f"• `edit portfolio {name}`" for name in portfolios]
    return "\n".join(lines)


def _config_footer(settings: Settings) -> str:
    if settings.portfolios:
        portfolios = ", ".join(f"`{name}`" for name in settings.portfolios)
        portfolio_line = f"• Portfolios: {portfolios}"
    else:
        portfolio_line = "• Portfolios: not set — add `PORTFOLIOS` to `.env`"
    return (
        f"\n\n*Your config (.env)*\n"
        f"{portfolio_line}\n"
        f"• Base currency: `{settings.base_currency}`"
    )


def build_start_message(settings: Settings) -> str:
    portfolio = portfolio_example(settings.portfolios, 0)
    return f"""\
Welcome to *Money Talks Bot*.

Add investment transactions to your Supabase database (same table as the Money Talks dashboard). Nothing is saved until you *confirm*.

*Send*
• *Photo* — broker screenshot (dividend/trade history)
• *File* — CSV or Excel (broker dividend export or Money Talks export)
• *Text* — manual entry (see `/add` or `/help`)

*Then*
1. Review the parsed draft (edit anything wrong).
2. Set portfolio if missing: `edit portfolio {portfolio}`
3. Reply `confirm` — or `reject` to discard.

*Commands*
/help — full guide
/add — manual entry format
/recent — last 10 saved rows (with ids)
/delete 432 — delete by id (see /recent)
/undo — delete last row saved this session
/pending — drafts waiting for confirmation
"""


def build_help_message(settings: Settings) -> str:
    portfolio = portfolio_example(settings.portfolios, 0)
    portfolio_alt = (
        portfolio_example(settings.portfolios, 1)
        if len(settings.portfolios) > 1
        else portfolio
    )
    manual_line = _manual_entry_line(settings.portfolios)
    edit_portfolio_lines = _portfolio_edit_examples(settings.portfolios)

    return f"""\
*Commands*

/start — welcome & quick overview
/help — this guide
/add — manual entry template
/recent — last 10 transactions (shows database ids)
/delete 432 — delete one row (get id from /recent)
/undo — delete the last row *you saved in this bot session*
/pending — list unconfirmed drafts

---

*1. Broker screenshot (photo)*

Send as a *photo* (not a file).

Supported layouts:
• *Mobile history* — Cash Dividend + Dividend Tax → one net DIVIDEND
• *Dividend table* — web/export style rows

Portfolio is never guessed. After parsing:
`edit portfolio {portfolio}` → `confirm`

Requires `GEMINI_API_KEY` in your bot `.env`.

---

*2. CSV / Excel (file)*

Send the file as a document.

• *Broker dividend CSV* — columns like Date, Symbol, Cash Dividends, Net Cash Value, Currency → action set to DIVIDEND automatically; you still add portfolio.
• *Money Talks export* — must include Date, Portfolio, Ticker, Action, Currency, Value (and optional Quantity).

Multiple rows are queued one at a time — confirm each before the next.

---

*3. Manual text entry*

One message with field pairs (`|` or spaces between fields):

```
{manual_line}
```

Colon format also works: `date: 2026-06-04 | portfolio: {portfolio} | ...`

This becomes the active draft immediately.

---

*4. Review, edit, save*

After any import, the bot shows a summary with *contextual* edit hints (your portfolios from `.env`, extracted values).

```
confirm
edit portfolio {portfolio_alt}
edit value 1.41
edit ticker AAPL
reject
```

Configured portfolios — reply with one of:
{edit_portfolio_lines}

*DIVIDEND* drafts: once portfolio is set, *quantity* is filled from your open holdings in the database (BUY − SELL). Override with `edit quantity 3` if needed.

*Duplicates:* if a similar row exists, you'll be warned. Reply `confirm anyway` to save anyway.

---

*5. Delete saved rows*

```
/recent
/delete 432
```

Or reply: `delete 432`

`/undo` only removes the last transaction saved in the current bot session (not the same as `/delete`).

---

*Security*

Only Telegram user ids listed in `ALLOWED_TELEGRAM_USER_IDS` can use this bot.
{_config_footer(settings)}
"""


def build_add_message(settings: Settings) -> str:
    manual_line = _manual_entry_line(settings.portfolios)
    return f"""\
*Manual entry*

Send one message like:

```
{manual_line}
```

Supported fields: `date`, `portfolio`, `action`, `ticker`, `currency`, `quantity`, `value`

Actions: `BUY`, `SELL`, `DIVIDEND`, `DEPOSIT`, `FEE`

Then review the draft and reply `confirm`.
"""


def manual_parse_error(portfolios: list[str]) -> str:
    portfolio = portfolio_example(portfolios, 0)
    return (
        f"Could not parse fields. Use: "
        f"`date 2026-06-04 | portfolio {portfolio} | action BUY | ...`"
    )


def edit_portfolio_hint(portfolios: list[str]) -> str:
    portfolio = portfolio_example(portfolios, 0)
    return f"Use `edit <field> <value>` (e.g. `edit portfolio {portfolio}`)."


def unknown_edit_format_hint(portfolios: list[str]) -> str:
    portfolio = portfolio_example(portfolios, 0)
    return (
        f"Unknown edit format. Example: `edit value 1.41` or "
        f"`edit portfolio {portfolio}`"
    )
