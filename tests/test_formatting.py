from src.formatting import format_transaction_summary
from src.models import ExtractedTransaction


def test_reply_hints_use_extracted_value_not_generic_default():
    draft = ExtractedTransaction(
        date="2026-06-01",
        action="DIVIDEND",
        ticker="V",
        quantity=3,
        currency="USD",
        value=1.41,
        source="vision",
    )
    draft.refresh_missing_fields()
    text = format_transaction_summary(draft)

    assert "edit value 1.41" in text
    assert "1850" not in text
    assert "edit portfolio Tiger" in text
    assert "edit portfolio MooMoo" in text
    assert "Portfolios (from your .env)" in text
