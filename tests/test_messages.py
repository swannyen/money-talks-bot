from src.config import Settings
from src.messages import (
    build_help_message,
    build_start_message,
    manual_example_line,
    portfolio_example,
)


def _settings(*, portfolios: list[str]) -> Settings:
    return Settings(
        telegram_bot_token="test",
        database_url="postgresql://localhost/test",
        allowed_telegram_user_ids=frozenset({1}),
        portfolios=portfolios,
        currencies=["SGD", "USD"],
        base_currency="SGD",
        gemini_api_key=None,
        gemini_model="gemini-2.5-flash",
    )


def test_portfolio_example_uses_env_names():
    assert portfolio_example(["Alpha", "Beta"], 0) == "Alpha"
    assert portfolio_example(["Alpha", "Beta"], 1) == "Beta"


def test_portfolio_example_falls_back_to_placeholder():
    assert portfolio_example([], 0) == "<Portfolio>"
    assert portfolio_example(["OnlyOne"], 2) == "<Portfolio>"


def test_help_message_uses_configured_portfolios():
    text = build_help_message(_settings(portfolios=["Alpha", "Beta"]))
    assert "edit portfolio Alpha" in text
    assert "portfolio Alpha" in text
    assert "edit portfolio Beta" in text
    assert "`Alpha`" in text and "`Beta`" in text
    assert "Tiger" not in text
    assert "Vickers" not in text


def test_help_message_uses_placeholder_when_no_portfolios():
    text = build_help_message(_settings(portfolios=[]))
    assert "edit portfolio <Portfolio>" in text
    assert "Portfolios: not set" in text


def test_start_message_uses_configured_portfolio():
    settings = _settings(portfolios=["MyBroker"])
    text = build_start_message(settings)
    assert "edit portfolio MyBroker" in text
    assert "/add" in text
    assert "/addsupport" in text
    assert "confirm" in text.lower()
    assert "How to add" in text


def test_help_message_documents_reminders():
    text = build_help_message(_settings(portfolios=["Alpha"]))
    assert "/remind" in text
    assert "monthly" in text.lower()
    assert "How to use" in text
    assert "/addsupport" in text


def test_start_message_lists_remind_command():
    text = build_start_message(_settings(portfolios=["Alpha"]))
    assert "/remind" in text
    assert "/help" in text
    assert "/addsupport" in text


def test_add_usage_message_shows_example_and_addsupport():
    from src.messages import build_add_usage_message

    text = build_add_usage_message(_settings(portfolios=["Tiger"]))
    assert "/add " in text
    assert "portfolio Tiger" in text
    assert "/addsupport" in text


def test_manual_example_line_uses_configured_portfolio():
    line = manual_example_line(["MyBroker"], action="BUY")
    assert "portfolio MyBroker" in line
    assert "action BUY" in line
