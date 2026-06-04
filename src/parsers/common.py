"""Shared spreadsheet parsing helpers."""

from __future__ import annotations

import re
from typing import Optional

import pandas as pd


def normalize_header(name: str) -> str:
    return re.sub(r"\s+", " ", str(name).strip().lower())


def build_header_map(columns: list[str], aliases: dict[str, list[str]]) -> dict[str, str]:
    normalized = {normalize_header(column): column for column in columns}
    mapping: dict[str, str] = {}
    for field, field_aliases in aliases.items():
        for alias in field_aliases:
            if alias in normalized:
                mapping[field] = normalized[alias]
                break
    return mapping


def parse_date(value) -> Optional[str]:
    if pd.isna(value):
        return None
    try:
        return pd.to_datetime(value).strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return None


def parse_int(value) -> Optional[int]:
    if pd.isna(value):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def parse_float(value) -> Optional[float]:
    if pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
