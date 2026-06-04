import pytest


@pytest.fixture(autouse=True)
def _test_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/postgres")
    monkeypatch.setenv("ALLOWED_TELEGRAM_USER_IDS", "123456789")
    monkeypatch.setenv("PORTFOLIOS", "Tiger,MooMoo,Vickers")
    get_settings = pytest.importorskip("src.config").get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
