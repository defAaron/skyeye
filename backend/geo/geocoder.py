"""Google Maps Geocoding API client. Never logs or returns the API key."""

from __future__ import annotations

import json
import logging
import ssl
import urllib.error
import urllib.parse
import urllib.request

from config import settings

logger = logging.getLogger(__name__)

GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
TIMEOUT_SECONDS = 12
USER_AGENT = "SkyEye/0.2 (RescueHacks SAR demo)"


class GeocodeProviderError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def _ssl_context() -> ssl.SSLContext:
    """python.org framework builds ship no system roots; certifi comes with the venv."""
    try:
        import certifi
    except ImportError:
        return ssl.create_default_context()
    return ssl.create_default_context(cafile=certifi.where())


def geocode_address(location_text: str) -> tuple[float, float, str]:
    key = settings.google_maps_api_key
    if not key:
        raise GeocodeProviderError(
            503,
            "GEOCODE_UNAVAILABLE",
            "Geocoding is not configured on this server.",
        )

    query = urllib.parse.urlencode({"address": location_text, "key": key})
    request = urllib.request.Request(
        f"{GEOCODE_URL}?{query}",
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
    )

    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS, context=_ssl_context()) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError:
        logger.warning("geocode provider HTTP error for query_len=%d", len(location_text))
        raise GeocodeProviderError(
            502,
            "GEOCODE_FAILED",
            "The geocoding provider rejected the request.",
        ) from None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError):
        logger.warning("geocode provider unreachable or returned non-JSON")
        raise GeocodeProviderError(
            502,
            "GEOCODE_FAILED",
            "The geocoding provider could not be reached.",
        ) from None

    status = str(payload.get("status") or "")
    # Google's error_message sometimes echoes the key — never forward it.
    if status == "OK":
        results = payload.get("results") or []
        if not results:
            raise GeocodeProviderError(
                404,
                "GEOCODE_NOT_FOUND",
                "No map location matched that description.",
            )
        first = results[0]
        geometry = (first.get("geometry") or {}).get("location") or {}
        try:
            lat = float(geometry["lat"])
            lng = float(geometry["lng"])
        except (KeyError, TypeError, ValueError):
            raise GeocodeProviderError(
                502,
                "GEOCODE_FAILED",
                "The geocoding provider returned an unusable result.",
            ) from None
        formatted = str(first.get("formatted_address") or location_text)
        logger.info("geocode ok query_len=%d", len(location_text))
        return lat, lng, formatted

    if status in {"ZERO_RESULTS", "NOT_FOUND"}:
        raise GeocodeProviderError(
            404,
            "GEOCODE_NOT_FOUND",
            "No map location matched that description.",
        )
    if status in {"REQUEST_DENIED", "OVER_DAILY_LIMIT", "OVER_QUERY_LIMIT"}:
        logger.warning("geocode provider denied request status=%s", status)
        raise GeocodeProviderError(
            503,
            "GEOCODE_UNAVAILABLE",
            "Geocoding is not available. Check that the Geocoding API is enabled for this key.",
        )
    if status == "INVALID_REQUEST":
        raise GeocodeProviderError(
            400,
            "EMPTY_LOCATION",
            "That location description could not be geocoded.",
        )

    logger.warning("geocode provider unexpected status=%s", status)
    raise GeocodeProviderError(
        502,
        "GEOCODE_FAILED",
        "The geocoding provider returned an unexpected status.",
    )
