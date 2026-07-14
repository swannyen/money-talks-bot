import pytest


@pytest.fixture(autouse=True)
def _test_env(monkeypatch, tmp_path):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/postgres")
    monkeypatch.setenv("ALLOWED_TELEGRAM_USER_IDS", "123456789")
    monkeypatch.setenv("PORTFOLIOS", "Tiger,MooMoo,Vickers")
    monkeypatch.setenv("REMINDER_STORE_PATH", str(tmp_path / "reminders.json"))
    get_settings = pytest.importorskip("src.config").get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
