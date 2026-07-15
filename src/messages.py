"""Telegram bot copy — built from settings so examples match each user's `.env`."""

from __future__ import annotations

from src.config import ACCEPTED_ACTIONS, Settings


def portfolio_example(portfolios: list[str], index: int = 0) -> str:
    """Portfolio name for examples, or ``<Portfolio>`` when none are configured."""
    if portfolios and index < len(portfolios):
        return portfolios[index]
    return "<Portfolio>"


def portfolio_edit_hints(portfolios: list[str]) -> list[str]:
    if not portfolios:
        return ["• `edit portfolio <Portfolio>`"]
    return [f"• `edit portfolio {name}`" for name in portfolios]


def manual_example_line(portfolios: list[str], *, action: str = "BUY") -> str:
    portfolio = portfolio_example(portfolios, 0)
    examples = {
        "BUY": (
            f"date 2026-06-04 | portfolio {portfolio} | action BUY | "
            f"ticker AAPL | currency USD | quantity 10 | value 1850"
        ),
        "SELL": (
            f"date 2026-06-04 | portfolio {portfolio} | action SELL | "
            f"ticker AAPL | currency USD | quantity 5 | value 920"
        ),
        "DIVIDEND": (
            f"date 2026-06-01 | portfolio {portfolio} | action DIVIDEND | "
            f"ticker V | currency USD | quantity 3 | value 1.41"
        ),
        "FEE": (
            f"date 2026-06-01 | portfolio {portfolio} | action FEE | "
            f"ticker V | currency USD | value 0.60"
        ),
    }
    return examples.get(action, examples["BUY"])


def _portfolio_edit_examples(portfolios: list[str]) -> str:
    return "\n".join(portfolio_edit_hints(portfolios))


def _config_footer(settings: Settings) -> str:
    if settings.portfolios:
        portfolios = ", ".join(f"`{name}`" for name in settings.portfolios)
        portfolio_line = f"• Portfolios: {portfolios}"
    else:
        portfolio_line = "• Portfolios: not set — add `PORTFOLIOS` to `.env`"
    return (
        f"\n\n*Your config (.env)*\n"
        f"{portfolio_line}\n"
        f"• Base currency: `{settings.base_currency}`\n"
        f"• Reminder timezone: `{settings.reminder_timezone}`"
    )


def build_add_usage_message(settings: Settings) -> str:
    example = manual_example_line(settings.portfolios)
    return (
        "*Manual add* — put the fields after `/add`:\n\n"
        f"`/add {example}`\n\n"
        f"Actions: {', '.join(ACCEPTED_ACTIONS)}.\n"
        "For the button flow, send `/addsupport` instead."
    )


def build_start_message(settings: Settings) -> str:
    portfolio = portfolio_example(settings.portfolios, 0)
    example = manual_example_line(settings.portfolios)
    return f"""\
Welcome to *Money Talks Bot*.

I save investment transactions to your Money Talks database. *Nothing is written until you confirm.*

*How to add a transaction*

1. Choose a way to enter it:
   • `/add …` — one-line manual fields (example below)
   • `/addsupport` — guided steps with buttons
   • *Photo* — broker screenshot
   • *File* — CSV / Excel export
2. Check the draft summary.
3. Fix anything wrong, e.g. `edit portfolio {portfolio}`
4. Reply `confirm` to save, or `reject` to discard.

*Manual example*
`/add {example}`

*Useful commands*
/help — full guide
/add — manual one-line add
/addsupport — add with buttons
/remind — reminder schedule
/recent — last 10 saved rows
/delete 432 — delete by id
/undo — undo last save *this session*
"""


def build_help_message(settings: Settings) -> str:
    portfolio = portfolio_example(settings.portfolios, 0)
    portfolio_alt = (
        portfolio_example(settings.portfolios, 1) if len(settings.portfolios) > 1 else portfolio
    )
    manual_line = manual_example_line(settings.portfolios)
    edit_portfolio_lines = _portfolio_edit_examples(settings.portfolios)

    return f"""\
*How to use Money Talks Bot*

Nothing is saved until you reply `confirm`. If something looks wrong, `edit …` or `reject`.

---

*Manual add (`/add`)*

Put the fields on the same line after `/add`:

```
/add {manual_line}
```

Colon style also works after `/add`:
`/add date: 2026-06-04 | portfolio: {portfolio} | …`

Actions: {', '.join(ACCEPTED_ACTIONS)}.
You can still paste the field line *without* `/add` as a normal message.

---

*Button add (`/addsupport`)*

1. Send `/addsupport`
2. Tap the type (BUY, SELL, DIVIDEND, FEE, DEPOSIT)
3. Follow the buttons for portfolio, date, ticker, amount, etc.
4. Tap *Confirm* (or type `confirm`) to save

DIVIDEND offers holdings to tap. DEPOSIT skips ticker (set to `NA`).

---

*Photo & files*

*Photo* — send a broker screenshot as a *photo* (not a document). Best for dividend layouts. Portfolio is not guessed — set it after parsing:
`edit portfolio {portfolio}` → `confirm`

*CSV / Excel* — send as a document.
• Broker dividend CSV (Date, Symbol, dividends, currency, …) → action DIVIDEND; still set portfolio
• Money Talks export → needs Date, Portfolio, Ticker, Action, Currency, Value

Several rows are queued — confirm one, then the next.

---

*Review & edit*

After any entry you get a summary. Common replies:

```
confirm
reject
edit portfolio {portfolio_alt}
edit value 1.41
edit ticker AAPL
edit quantity 3
```

Your portfolios:
{edit_portfolio_lines}

*DIVIDEND:* quantity can auto-fill from holdings (BUY − SELL) once portfolio is set.
*Duplicates:* if a similar row exists, reply `confirm anyway` to save anyway.

---

*Find & delete*

```
/recent          → see ids
/delete 432      → delete that row
delete 432       → same, as a text reply
/undo            → delete last row saved *in this bot session*
```

---

*Reminders*

The bot can ping you to log updates.
Default: *monthly on the 15th at 20:00* (`{settings.reminder_timezone}`).

• `/remind` — frequency (daily / weekly / every 2 weeks / monthly), day, or time
• `/remind off` / `/remind on` — disable or re-enable

Reminders start (with defaults) the first time you send `/start`.

---

*Commands*

/start — this overview
/help — this guide
/add — manual one-line add
/addsupport — guided add with buttons
/remind — reminder settings
/recent — last 10 transactions
/delete 432 — delete by id
/undo — undo last session save

*Security:* only user ids in `ALLOWED_TELEGRAM_USER_IDS` can use this bot.
{_config_footer(settings)}
"""


def manual_parse_error(portfolios: list[str]) -> str:
    example = manual_example_line(portfolios, action="SELL")
    return (
        f"Could not parse fields. Example:\n`{example}`\n"
        f"Actions: {', '.join(ACCEPTED_ACTIONS)}. See `/help` for more."
    )


def edit_portfolio_hint(portfolios: list[str]) -> str:
    portfolio = portfolio_example(portfolios, 0)
    return f"Use `edit <field> <value>` (e.g. `edit portfolio {portfolio}`)."


def unknown_edit_format_hint(portfolios: list[str]) -> str:
    portfolio = portfolio_example(portfolios, 0)
    return f"Unknown edit format. Example: `edit value 1.41` or " f"`edit portfolio {portfolio}`"
