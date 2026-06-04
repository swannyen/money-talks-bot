"""Parse user edit commands like: edit value 1850"""

from __future__ import annotations

import re
from typing import Optional

from pydantic import ValidationError

from src.models import ExtractedTransaction

EDIT_PATTERN = re.compile(
    r"^edit\s+(date|portfolio|action|ticker|quantity|currency|value)\s+(.+)$",
    re.IGNORECASE,
)

FIELD_SETTERS = {
    "date": lambda d, v: d.model_copy(update={"date": v.strip()}),
    "portfolio": lambda d, v: d.model_copy(update={"portfolio": v.strip()}),
    "action": lambda draft, value: draft.model_copy(
        update={"action": value.strip().upper()}  # type: ignore[arg-type]
    ),
    "ticker": lambda d, v: d.model_copy(update={"ticker": v.strip()}),
    "quantity": lambda d, v: d.model_copy(update={"quantity": int(float(v))}),
    "currency": lambda d, v: d.model_copy(update={"currency": v.strip().upper()}),
    "value": lambda d, v: d.model_copy(update={"value": float(v)}),
}


def apply_edit(
    draft: ExtractedTransaction, message: str
) -> tuple[Optional[ExtractedTransaction], Optional[str]]:
    match = EDIT_PATTERN.match(message.strip())
    if not match:
        return None, None

    field, raw_value = match.group(1).lower(), match.group(2)
    try:
        updated = FIELD_SETTERS[field](draft, raw_value)
        updated.refresh_missing_fields()
        return updated, None
    except (ValidationError, ValueError) as exc:
        return None, str(exc)
