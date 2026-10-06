"""Broker screenshot extraction via Gemini vision."""

from __future__ import annotations

import json
import logging
import re
from typing import Optional

from src.config import get_settings
from src.models import ExtractedTransaction
from src.parsers.vision_mapping import parse_vision_payload
from src.parsers.prompts import INVESTMENT_EXTRACTION_SYSTEM, INVESTMENT_EXTRACTION_USER

logger = logging.getLogger(__name__)


class VisionParserError(Exception):
    pass


class VisionNotConfiguredError(VisionParserError):
    pass


def _extract_json_object(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise VisionParserError("Model did not return valid JSON") from exc


def parse_vision_response(raw: dict) -> list[ExtractedTransaction]:
    return parse_vision_payload(raw)


def extract_transactions_from_image(
    image_bytes: bytes,
    *,
    mime_type: str = "image/jpeg",
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> list[ExtractedTransaction]:
    settings = get_settings()
    key = api_key or settings.gemini_api_key
    if not key:
        raise VisionNotConfiguredError(
            "GEMINI_API_KEY is not set. Add it to .env for screenshot parsing."
        )

    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise VisionParserError(
            "google-genai is not installed. Run: pip install google-genai"
        ) from exc

    client = genai.Client(api_key=key)
    user_prompt = INVESTMENT_EXTRACTION_USER.format(
        portfolios=", ".join(settings.portfolios),
        currencies=", ".join(settings.currencies),
    )

    response = client.models.generate_content(
        model=model or settings.gemini_model,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            user_prompt,
        ],
        config=types.GenerateContentConfig(
            system_instruction=INVESTMENT_EXTRACTION_SYSTEM,
            temperature=0.1,
            max_output_tokens=4096,
            response_mime_type="application/json",
        ),
    )

    raw_text = (response.text or "").strip()
    if not raw_text:
        raise VisionParserError("Empty response from vision model")

    logger.info("Vision extraction completed (bytes=%s, mime=%s)", len(image_bytes), mime_type)
    payload = _extract_json_object(raw_text)
    drafts = parse_vision_response(payload)
    if not drafts:
        raise VisionParserError("No transactions found in screenshot")
    return drafts
