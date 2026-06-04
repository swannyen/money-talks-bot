"""Parse free-form manual transaction messages."""

from __future__ import annotations

import re
from typing import Optional

from pydantic import ValidationError

from src.config import get_settings
from src.messages import manual_parse_error
from src.models import ExtractedTransaction

FIELD_NAMES = frozenset({"date", "portfolio", "action", "ticker", "currency", "quantity", "value"})


def _looks_like_manual_entry(text: str) -> bool:
    lower = text.lower()
    if "|" in text:
        return True
    return sum(name in lower for name in ("portfolio", "action", "ticker", "value")) >= 2


def _parse_segment(segment: str, data: dict[str, str]) -> None:
    segment = segment.strip()
    if not segment:
        return

    if ":" in segment:
        key, _, raw_value = segment.partition(":")
        key = key.strip().lower()
        value = raw_value.strip()
        if key in FIELD_NAMES and value:
            data[key] = value
        return

    tokens = segment.split()
    index = 0
    while index < len(tokens) - 1:
        key = tokens[index].lower()
        if key not in FIELD_NAMES:
            index += 1
            continue
        index += 1
        value_tokens: list[str] = []
        while index < len(tokens) and tokens[index].lower() not in FIELD_NAMES:
            value_tokens.append(tokens[index])
            index += 1
        if value_tokens:
            data[key] = " ".join(value_tokens)


def parse_manual_fields(text: str) -> dict[str, str]:
    data: dict[str, str] = {}
    segments = [part.strip() for part in text.split("|")] if "|" in text else [text]
    for segment in segments:
        _parse_segment(segment, data)
    if data:
        return data

    # Fallback: token walk across the whole line
    parts = [part for part in re.split(r"\s+", text.strip()) if part]
    index = 0
    while index < len(parts) - 1:
        key = parts[index].lower()
        if key in FIELD_NAMES:
            data[key] = parts[index + 1]
            index += 2
        else:
            index += 1
    return data


def parse_manual_line(text: str) -> tuple[Optional[ExtractedTransaction], Optional[str]]:
    if not _looks_like_manual_entry(text):
        return None, None

    data = parse_manual_fields(text)
    if not data:
        return (None, manual_parse_error(get_settings().portfolios))

    try:
        action_raw = data.get("action")
        draft = ExtractedTransaction(
            date=data.get("date", ""),
            portfolio=data.get("portfolio"),
            action=action_raw.upper() if action_raw else None,  # type: ignore[arg-type]
            ticker=data.get("ticker"),
            quantity=int(float(data["quantity"])) if data.get("quantity") else None,
            currency=data.get("currency"),
            value=float(data["value"]) if data.get("value") else None,
            source="manual",
        )
        draft.refresh_missing_fields()
        return draft, None
    except (ValidationError, ValueError, TypeError) as exc:
        return None, f"Invalid manual entry: {exc}"
