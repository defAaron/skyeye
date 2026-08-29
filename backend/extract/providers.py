"""Gemini primary + Groq fallback. Never logs keys or the report body."""

from __future__ import annotations

import json
import logging
import ssl
import urllib.error
import urllib.request

from config import settings
from extract.normalize import ExtractNormalizeError, normalize
from geo.lpb import CATEGORIES
from ratelimit import acquire_gemini, acquire_groq, trip_gemini_cooldown, trip_groq_cooldown

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 12
USER_AGENT = "SkyEye/0.3 (RescueHacks SAR demo)"

# Gemini 2.0 Flash (and 2.5 Flash on many keys) retired June 2026.
# Try the moving alias first, then the documented 3.x Flash replacements.
GEMINI_MODELS = ("gemini-flash-latest", "gemini-3.5-flash", "gemini-3.1-flash-lite")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODELS = ("llama-3.1-8b-instant", "llama-3.3-70b-versatile")

SYSTEM_PROMPT = (
    "You extract structured facts from a missing-person report for a search-and-rescue "
    "triage tool. Return JSON only. Do not confirm anyone's location or safety. "
    "Never use the words found, located, or confirmed.\n"
    "location_text: a short geocodable place from the report (trail, park, town). "
    "Do not invent a place that was not mentioned. Use an empty string if none.\n"
    "time_last_seen: 24-hour HH:MM if a clock time is given, otherwise null.\n"
    "elapsed_hours: hours since last seen. If the report gives a clock time but no "
    "elapsed hours, estimate assuming it is now 19:30 local. If no time is given, use 3.0.\n"
    "subject.age: integer years or null. clothing and distinguishing_features: short "
    "strings or null.\n"
    "subject.category: exactly one of "
    + ", ".join(CATEGORIES)
    + ". Use elderly_hiker for an older adult on a trail. Use unknown if unsure.\n"
    "terrain_hint: short terrain phrase or null."
)

GEMINI_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "location_text": {"type": "STRING"},
        "time_last_seen": {"type": "STRING", "nullable": True},
        "elapsed_hours": {"type": "NUMBER"},
        "subject": {
            "type": "OBJECT",
            "properties": {
                "age": {"type": "INTEGER", "nullable": True},
                "clothing": {"type": "STRING", "nullable": True},
                "distinguishing_features": {"type": "STRING", "nullable": True},
                "category": {"type": "STRING"},
            },
            "required": ["category"],
        },
        "terrain_hint": {"type": "STRING", "nullable": True},
    },
    "required": ["location_text", "elapsed_hours", "subject"],
}


class ExtractProviderError(Exception):
    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        retry_after: int | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.retry_after = retry_after


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi
    except ImportError:
        return ssl.create_default_context()
    return ssl.create_default_context(cafile=certifi.where())


def _post_json(url: str, headers: dict[str, str], payload: dict) -> tuple[int, dict | None]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
            **headers,
        },
    )
    try:
        with urllib.request.urlopen(
            request, timeout=TIMEOUT_SECONDS, context=_ssl_context()
        ) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw)
    except urllib.error.HTTPError as exc:
        try:
            json.loads(exc.read().decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
            pass
        # Body is discarded: provider error_message can echo the API key.
        return exc.code, None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError):
        return 0, None


def _parse_json_text(text: str) -> object:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()
    return json.loads(cleaned)


def _gemini_url(model: str) -> str:
    return f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def _gemini(report_text: str) -> dict:
    key = settings.gemini_api_key
    last_status = 0
    saw_quota = False
    for model in GEMINI_MODELS:
        allowed, retry_after = acquire_gemini()
        if not allowed:
            logger.info("extract gemini skipped reason=rate_limit retry_after=%s", retry_after)
            raise ExtractProviderError(
                429,
                "RATE_LIMITED",
                "The primary extraction provider is at its local rate limit.",
                retry_after=retry_after,
            )
        status, payload = _post_json(
            _gemini_url(model),
            {"x-goog-api-key": key},
            {
                "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                "contents": [{"role": "user", "parts": [{"text": report_text}]}],
                "generationConfig": {
                    "temperature": 0.1,
                    "responseMimeType": "application/json",
                    "responseSchema": GEMINI_RESPONSE_SCHEMA,
                },
            },
        )
        last_status = status
        if status in {400, 404}:
            logger.warning("extract gemini model rejected model=%s status=%s", model, status)
            continue
        if status in {401, 403}:
            raise ExtractProviderError(
                503,
                "EXTRACT_UNAVAILABLE",
                "The primary extraction provider denied the request.",
            )
        if status == 429:
            # Per-model free-tier exhaustion is common; try the next id before
            # treating the whole key as spent.
            saw_quota = True
            logger.warning("extract gemini model at quota model=%s", model)
            continue
        if status != 200 or not isinstance(payload, dict):
            raise ExtractProviderError(
                502,
                "EXTRACT_FAILED",
                "The primary extraction provider could not be reached.",
            )

        try:
            text = payload["candidates"][0]["content"]["parts"][0]["text"]
            parsed = _parse_json_text(text)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError):
            raise ExtractProviderError(
                502,
                "EXTRACT_FAILED",
                "The primary extraction provider returned unusable output.",
            ) from None

        try:
            return normalize(parsed, "gemini")
        except ExtractNormalizeError as exc:
            raise ExtractProviderError(400, exc.code, exc.message) from None

    if saw_quota:
        trip_gemini_cooldown()
        raise ExtractProviderError(
            503,
            "EXTRACT_UNAVAILABLE",
            "The primary extraction provider is at quota.",
            retry_after=settings.gemini_cooldown_seconds,
        )
    raise ExtractProviderError(
        502 if last_status not in {401, 403} else 503,
        "EXTRACT_FAILED" if last_status not in {401, 403} else "EXTRACT_UNAVAILABLE",
        "The primary extraction provider could not be reached.",
    )


def _groq(report_text: str) -> dict:
    key = settings.groq_api_key
    last_status = 0
    for model in GROQ_MODELS:
        allowed, retry_after = acquire_groq()
        if not allowed:
            logger.info("extract groq skipped reason=rate_limit retry_after=%s", retry_after)
            raise ExtractProviderError(
                429,
                "RATE_LIMITED",
                "The fallback extraction provider is at its local rate limit.",
                retry_after=retry_after,
            )
        status, payload = _post_json(
            GROQ_URL,
            {"Authorization": f"Bearer {key}"},
            {
                "model": model,
                "temperature": 0.1,
                "response_format": {"type": "json_object"},
                "messages": [
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT + " Respond with a JSON object.",
                    },
                    {"role": "user", "content": report_text},
                ],
            },
        )
        last_status = status
        if status in {400, 404}:
            logger.warning("extract groq model rejected status=%s", status)
            continue
        if status in {401, 403}:
            raise ExtractProviderError(
                503,
                "EXTRACT_UNAVAILABLE",
                "The fallback extraction provider denied the request.",
            )
        if status == 429:
            trip_groq_cooldown()
            raise ExtractProviderError(
                503,
                "EXTRACT_UNAVAILABLE",
                "The fallback extraction provider is at quota.",
                retry_after=settings.groq_cooldown_seconds,
            )
        if status != 200 or not isinstance(payload, dict):
            raise ExtractProviderError(
                502,
                "EXTRACT_FAILED",
                "The fallback extraction provider could not be reached.",
            )

        try:
            text = payload["choices"][0]["message"]["content"]
            parsed = _parse_json_text(text)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError):
            raise ExtractProviderError(
                502,
                "EXTRACT_FAILED",
                "The fallback extraction provider returned unusable output.",
            ) from None

        try:
            return normalize(parsed, "groq")
        except ExtractNormalizeError as exc:
            raise ExtractProviderError(400, exc.code, exc.message) from None

    raise ExtractProviderError(
        502 if last_status not in {401, 403, 429} else 503,
        "EXTRACT_FAILED" if last_status not in {401, 403, 429} else "EXTRACT_UNAVAILABLE",
        "The fallback extraction provider could not be reached.",
    )


def extract_report(report_text: str) -> dict:
    if not settings.extract_configured:
        raise ExtractProviderError(
            503,
            "EXTRACT_UNAVAILABLE",
            "Report extraction is not configured on this server.",
        )

    last_error: ExtractProviderError | None = None
    if settings.gemini_configured:
        try:
            result = _gemini(report_text)
            logger.info("extract ok provider=gemini report_len=%d", len(report_text))
            return result
        except ExtractProviderError as exc:
            last_error = exc
            if exc.code == "RATE_LIMITED":
                logger.info(
                    "extract gemini skipped code=RATE_LIMITED report_len=%d",
                    len(report_text),
                )
            else:
                logger.warning(
                    "extract gemini failed code=%s report_len=%d",
                    exc.code,
                    len(report_text),
                )
            if exc.code == "EXTRACT_INCOMPLETE" and not settings.groq_configured:
                raise

    if settings.groq_configured:
        try:
            result = _groq(report_text)
            logger.info("extract ok provider=groq report_len=%d", len(report_text))
            return result
        except ExtractProviderError as exc:
            last_error = exc
            if exc.code == "RATE_LIMITED":
                logger.info(
                    "extract groq skipped code=RATE_LIMITED report_len=%d",
                    len(report_text),
                )
            else:
                logger.warning(
                    "extract groq failed code=%s report_len=%d",
                    exc.code,
                    len(report_text),
                )
            raise

    if last_error is not None:
        raise last_error
    raise ExtractProviderError(
        502,
        "EXTRACT_FAILED",
        "Report extraction could not be completed.",
    )
