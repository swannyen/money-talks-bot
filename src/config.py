import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

DEFAULT_PORTFOLIOS = ["Tiger", "MooMoo", "Vickers"]
DEFAULT_CURRENCIES = ["SGD", "USD", "HKD", "EUR", "JPY"]
DEFAULT_BASE_CURRENCY = "SGD"
DEFAULT_REMINDER_TIMEZONE = "Asia/Singapore"
DEFAULT_REMINDER_STORE_PATH = _PROJECT_ROOT / "data" / "reminders.json"
ACCEPTED_ACTIONS = ("FEE", "BUY", "SELL", "DIVIDEND", "DEPOSIT")


def _parse_int_list(raw: str | None) -> list[int]:
    if not raw:
        return []
    return [int(part.strip()) for part in raw.split(",") if part.strip()]


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1].strip()
    return value


def _parse_str_list(raw: str | None, default: list[str]) -> list[str]:
    if raw is None:
        return default.copy()
    raw = _strip_quotes(raw)
    if not raw:
        return default.copy()
    return [_strip_quotes(item) for item in raw.split(",") if item.strip()]


@lru_cache
def get_settings() -> "Settings":
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")

    allowed_ids = _parse_int_list(os.getenv("ALLOWED_TELEGRAM_USER_IDS"))
    if not allowed_ids:
        raise RuntimeError(
            "ALLOWED_TELEGRAM_USER_IDS is not set (comma-separated Telegram user IDs)"
        )

    reminder_path_raw = os.getenv("REMINDER_STORE_PATH")
    reminder_store_path = (
        Path(reminder_path_raw).expanduser() if reminder_path_raw else DEFAULT_REMINDER_STORE_PATH
    )

    return Settings(
        telegram_bot_token=token,
        database_url=database_url,
        allowed_telegram_user_ids=frozenset(allowed_ids),
        portfolios=_parse_str_list(os.getenv("PORTFOLIOS"), DEFAULT_PORTFOLIOS),
        currencies=_parse_str_list(os.getenv("CURRENCIES"), DEFAULT_CURRENCIES),
        base_currency=(os.getenv("BASE_CURRENCY") or DEFAULT_BASE_CURRENCY).strip().upper(),
        gemini_api_key=os.getenv("GEMINI_API_KEY") or None,
        gemini_model=(os.getenv("GEMINI_MODEL") or "gemini-2.5-flash").strip(),
        reminder_timezone=(os.getenv("REMINDER_TIMEZONE") or DEFAULT_REMINDER_TIMEZONE).strip(),
        reminder_store_path=reminder_store_path,
    )


class Settings:
    def __init__(
        self,
        *,
        telegram_bot_token: str,
        database_url: str,
        allowed_telegram_user_ids: frozenset[int],
        portfolios: list[str],
        currencies: list[str],
        base_currency: str,
        gemini_api_key: str | None,
        gemini_model: str,
        reminder_timezone: str = DEFAULT_REMINDER_TIMEZONE,
        reminder_store_path: Path = DEFAULT_REMINDER_STORE_PATH,
    ):
        self.telegram_bot_token = telegram_bot_token
        self.database_url = database_url
        self.allowed_telegram_user_ids = allowed_telegram_user_ids
        self.portfolios = portfolios
        self.currencies = currencies
        self.base_currency = base_currency
        self.gemini_api_key = gemini_api_key
        self.gemini_model = gemini_model
        self.reminder_timezone = reminder_timezone
        self.reminder_store_path = reminder_store_path
