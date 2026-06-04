# Money Talks Bot

Telegram bot for adding **investment transactions** to the same Supabase `transactions` table used by [Money Talks](../money-talks/) — with confirmation before every save.

Supports CSV/Excel uploads, broker screenshots (Gemini vision), and manual text entry.

## Quick start

```bash
cd money-talks-bot
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env: TELEGRAM_BOT_TOKEN, DATABASE_URL, ALLOWED_TELEGRAM_USER_IDS
python -m src.bot
```

Create a bot with [@BotFather](https://t.me/BotFather), paste the token into `.env`.

Get your Telegram user id from [@userinfobot](https://t.me/userinfobot) and add it to `ALLOWED_TELEGRAM_USER_IDS` in `.env`.

## Workflow

### Screenshot (dividend / trade)

1. Crop to one transaction row if possible (your Visa dividend example works as two crops).
2. Send as a **photo** in Telegram.
3. Bot extracts date, ticker, quantity, currency, value (defaults to **net cash** after tax when shown).
4. Add portfolio: `edit portfolio Tiger` then `confirm`.

### CSV / Excel

1. Export rows from your tracker.
2. Send the file to the bot.
3. Review each row — `confirm`, `edit value 1850`, or `reject`.
4. On duplicate detection, reply `confirm anyway` to force save.

**Broker dividend CSV** (see `tests/fixtures/tiger_dividend.csv` for an example):

`Date`, `Symbol`, `Quantity/Gross Rate`, `Cash Dividends`, `Fees & Tax`, `Net Cash Value`, `Currency`

→ Action is set to **DIVIDEND** automatically. You still add portfolio: `edit portfolio Tiger`.

**Money Talks tracker export:**

`Date`, `Portfolio`, `Ticker`, `Currency`, `Action`, `Quantity`, `Value`

## Commands

| Command | Description |
|---------|-------------|
| `/start` | How to use the bot |
| `/help` | Examples |
| `/add` | Manual pipe-separated format |
| `/recent` | Last 10 saved rows (with database ids) |
| `/delete 432` | Delete a row by id |
| `/undo` | Delete last saved row (this session) |
| `/pending` | Drafts awaiting confirmation |

## Environment variables

See `.env.example`. Never commit `.env`.

| Variable | Required | Notes |
|----------|----------|-------|
| `TELEGRAM_BOT_TOKEN` | Yes | From BotFather |
| `ALLOWED_TELEGRAM_USER_IDS` | Yes | Comma-separated Telegram user ids |
| `DATABASE_URL` | Yes | Supabase **pooler** URL (port 6543) |
| `PORTFOLIOS` | No | Must match Money Talks |
| `CURRENCIES` | No | Must match Money Talks |
| `BASE_CURRENCY` | No | Default `SGD` |
| `GEMINI_API_KEY` | For photos | Free tier via [Google AI Studio](https://aistudio.google.com/app/apikey) |
| `GEMINI_MODEL` | No | Default `gemini-2.5-flash` |

## LLM providers (Phase 2 — screenshots)

For **CSV/Excel you do not need an LLM** — pandas parses the file locally (free, private).

When you add broker screenshots:

| Provider | Free tier | Vision / OCR | Notes |
|----------|-----------|--------------|-------|
| **Google Gemini** (AI Studio) | Yes, no card | Yes | Best default for vision; rate limits (~10 RPM on Flash). [Pricing](https://ai.google.dev/gemini-api/docs/pricing). Not in EU/UK/CH on free tier. |
| **Groq** | Yes | Limited (Llama 4 Scout) | Fast text; vision models more limited |
| **OpenRouter** (`:free` models) | Some free models | Some | Good for experiments; limits change |
| **OpenAI** | ~$5 signup credit only | GPT-4o mini | Credit expires; not ongoing free |
| **Anthropic** | Small console credit | Claude | No permanent free API |
| **Ollama (local)** | Free | If model supports vision | Only while your machine runs |

**Recommendation:** Gemini 2.5 Flash via `GEMINI_API_KEY` when you reach Phase 2. Keep spreadsheet import LLM-free.

## Tests

```bash
make check          # black + pylint + pytest
make format         # auto-format with black
make lint           # pylint only
pytest
```

## Deployment (overview)

### Option 1 — Docker on a VPS (Railway, Fly.io, DigitalOcean)

```bash
docker build -t money-talks-bot .
docker run --env-file .env money-talks-bot
```

Uses **long polling** — one container process, in-memory pending state is fine.

### Option 2 — Managed container (Render / Railway)

Connect the repo, set env vars in the dashboard, deploy `python -m src.bot` as a worker service (not a web service).

Webhook-based serverless (Lambda/Cloud Functions) is possible but needs Redis/DB for pending state — not recommended until you need scale.

## Project layout

```
money-talks-bot/
  src/
    bot.py                 # Entrypoint (long polling)
    bot_state.py           # Shared DB + session singletons
    config.py              # Environment settings
    models.py              # Pydantic transaction drafts
    session.py             # In-memory pending confirmations
    messages.py            # /start, /help, /add copy (from .env)
    formatting.py          # Draft summaries and edit hints
    edit_commands.py       # parse "edit field value" replies
    handlers/              # Telegram command and message handlers
    parsers/               # CSV/Excel, manual text, vision (Gemini)
    services/              # Postgres, FX, holdings, duplicates, insert enrichment
  tests/
    fixtures/              # Sample CSV inputs for parser tests
    test_*.py
  .env.example
  Dockerfile
  Makefile
  requirements.txt
```

## Security

- Only `ALLOWED_TELEGRAM_USER_IDS` can use the bot.
- Uploaded files are parsed in memory; not stored on disk.
- Logs avoid file contents and secrets.
