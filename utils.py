"""Utility helpers for AarogyaAI."""

import re
from datetime import datetime

from langdetect import detect, DetectorFactory, LangDetectException

AGE_PATTERN = re.compile(r"^\d{1,3}$")
PIN_PATTERN = re.compile(r"^\d{6}$")


def validate_age(age: str) -> bool:
    return AGE_PATTERN.match(age) is not None and 0 < int(age) <= 120


def validate_pin(pin: str) -> bool:
    return PIN_PATTERN.match(pin) is not None


DetectorFactory.seed = 0

LANG_MAP = {
    "en": "English",
    "hi": "Hindi",
    "ta": "Tamil",
    "te": "Telugu",
    "bn": "Bengali",
    "gu": "Gujarati",
    "kn": "Kannada",
    "ml": "Malayalam",
    "mr": "Marathi",
    "pa": "Punjabi",
}


def detect_language(text: str) -> str:
    """Detect language of user text and return readable name."""
    try:
        code = detect(text)
        return LANG_MAP.get(code, "English")
    except LangDetectException:
        return "English"


def timestamp() -> str:
    return datetime.utcnow().isoformat()
