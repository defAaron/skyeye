"""Turn a model JSON blob into the frozen /api/extract response.

Never trusts the model on bounds. Empty location is a hard failure so geocode
is not called on invented or missing places.
"""

from __future__ import annotations

from geo.lpb import CATEGORIES

EXTRACT_DISCLAIMER = (
    "Extracted fields are a starting point for a responder to review. "
    "They are not verified facts."
)

PROVIDERS = ("gemini", "groq")
MAX_LOCATION_CHARS = 200
MAX_SHORT_CHARS = 32
MAX_CLOTHING_CHARS = 120
MAX_FEATURES_CHARS = 200
MAX_TERRAIN_CHARS = 120
MIN_ELAPSED_HOURS = 0.1
MAX_ELAPSED_HOURS = 72.0
DEFAULT_ELAPSED_HOURS = 3.0


class ExtractNormalizeError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _clip_str(value: object, max_chars: int) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    text = " ".join(value.split()).strip()
    if not text:
        return None
    return text[:max_chars]


def _elapsed_hours(raw: object) -> float:
    try:
        hours = float(raw)
    except (TypeError, ValueError):
        return DEFAULT_ELAPSED_HOURS
    if hours != hours:  # NaN
        return DEFAULT_ELAPSED_HOURS
    return round(min(MAX_ELAPSED_HOURS, max(MIN_ELAPSED_HOURS, hours)), 1)


def _age(raw: object) -> int | None:
    if raw is None or raw == "":
        return None
    try:
        age = int(float(raw))
    except (TypeError, ValueError):
        return None
    if not 0 <= age <= 120:
        return None
    return age


def _category(raw: object) -> str:
    if isinstance(raw, str) and raw in CATEGORIES:
        return raw
    return "unknown"


def normalize(raw: object, provider: str) -> dict:
    if provider not in PROVIDERS:
        raise ExtractNormalizeError("EXTRACT_FAILED", "Unknown extraction provider.")
    if not isinstance(raw, dict):
        raise ExtractNormalizeError(
            "EXTRACT_INCOMPLETE",
            "The report did not include a usable last-known place.",
        )

    location = _clip_str(raw.get("location_text"), MAX_LOCATION_CHARS)
    if not location:
        raise ExtractNormalizeError(
            "EXTRACT_INCOMPLETE",
            "The report did not include a usable last-known place.",
        )

    subject_raw = raw.get("subject") if isinstance(raw.get("subject"), dict) else {}
    category = _category(subject_raw.get("category") or raw.get("category"))

    return {
        "location_text": location,
        "time_last_seen": _clip_str(raw.get("time_last_seen"), MAX_SHORT_CHARS),
        "elapsed_hours": _elapsed_hours(raw.get("elapsed_hours")),
        "subject": {
            "age": _age(subject_raw.get("age")),
            "clothing": _clip_str(subject_raw.get("clothing"), MAX_CLOTHING_CHARS),
            "distinguishing_features": _clip_str(
                subject_raw.get("distinguishing_features"), MAX_FEATURES_CHARS
            ),
            "category": category,
        },
        "terrain_hint": _clip_str(raw.get("terrain_hint"), MAX_TERRAIN_CHARS),
        "provider": provider,
        "disclaimer": EXTRACT_DISCLAIMER,
    }
