from unittest.mock import MagicMock, patch

from src.services.fx import convert_value_to_base, get_fx_rate


def test_same_currency_rate_is_one():
    assert get_fx_rate("SGD", "SGD") == 1.0


@patch("src.services.fx.requests.get")
def test_get_fx_rate_frankfurter(mock_get):
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"rates": {"USD": 0.78}},
    )
    mock_get.return_value.raise_for_status = MagicMock()

    assert get_fx_rate("USD", "SGD") == 0.78


@patch("src.services.fx.get_fx_rate", return_value=0.78)
def test_convert_value_to_base(mock_rate):
    del mock_rate
    result = convert_value_to_base(780.0, "USD", "SGD")
    assert round(result, 2) == 1000.0
