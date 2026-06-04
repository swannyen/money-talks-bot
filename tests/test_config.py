from src.config import _parse_str_list


def test_parse_portfolios_strips_quotes():
    assert _parse_str_list('"Alpha,Beta"', []) == ["Alpha", "Beta"]
    assert _parse_str_list("Tiger, MooMoo", []) == ["Tiger", "MooMoo"]
