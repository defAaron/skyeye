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

TIMEOUT_SECONDS = 20
USER_AGENT = "SkyEye/0.3 (RescueHacks SAR demo)"

# Gemini 2.0 Flash retired June 2026. Prefer current free-tier Flash IDs
# (AI Studio pricing as of Aug 2026), then the moving alias.
GEMINI_MODELS = (
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-flash-latest",
)
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
# Llama 3.1 8B Instant and Llama 3.3 70B Versatile shut down 16 Aug 2026
# for free/developer tiers. GPT-OSS is Groq's documented replacement.
GROQ_MODELS = ("openai/gpt-oss-20b", "openai/gpt-oss-120b")

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


def _provider_error_reason(payload: dict | None) -> str:
    """Safe Google/Groq error token for logs. Never the message — it can echo a key."""
    if not isinstance(payload, dict):
        return "unknown"
    err = payload.get("error")
    if not isinstance(err, dict):
        return "unknown"
    status = err.get("status")
    if isinstance(status, str) and status.replace("_", "").isalnum():
        return status
    code = err.get("code")
    if isinstance(code, int):
        return str(code)
    return "unknown"


def _post_json(url: str, headers: dict[str, str], payload: dict) -> tuple[int, dict | None, str]:
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
            return response.status, json.loads(raw), "ok"
    except urllib.error.HTTPError as exc:
        parsed: dict | None
        try:
            parsed = json.loads(exc.read().decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
            parsed = None
        return exc.code, None, _provider_error_reason(parsed)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError):
        return 0, None, "unreachable"


def _parse_json_text(text: str) -> object:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()
    return json.loads(cleaned)


def _choice_text(payload: dict) -> str:
    """Groq/OpenAI chat content, including gpt-oss array-of-parts payloads."""
    message = payload["choices"][0]["message"]
    content = message.get("content")
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str) and part.strip():
                parts.append(part)
            elif isinstance(part, dict):
                text = part.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text)
        content = "\n".join(parts)
    if isinstance(content, str) and content.strip():
        return content
    raise TypeError("empty groq content")


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
        status, payload, reason = _post_json(
            _gemini_url(model),
            {"x-goog-api-key": key},
            {
                "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                "contents": [{"role": "user", "parts": [{"text": report_text}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "responseSchema": GEMINI_RESPONSE_SCHEMA,
                },
            },
        )
        last_status = status
        if status in {400, 404}:
            logger.warning(
                "extract gemini model rejected model=%s status=%s reason=%s",
                model,
                status,
                reason,
            )
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
            logger.warning(
                "extract gemini model at quota model=%s reason=%s", model, reason
            )
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
        status, payload, reason = _post_json(
            GROQ_URL,
            {"Authorization": f"Bearer {key}"},
            {
                "model": model,
                "reasoning_effort": "low",
                "include_reasoning": False,
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
            logger.warning(
                "extract groq model rejected model=%s status=%s reason=%s",
                model,
                status,
                reason,
            )
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
            text = _choice_text(payload)
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
