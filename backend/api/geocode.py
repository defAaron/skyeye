from __future__ import annotations

from flask import Blueprint, jsonify, request

from api.errors import ApiError
from geo.geocoder import GeocodeProviderError, geocode_address
from geo.lpb import CATEGORIES, LPB_NOTE, radius_m
from ratelimit import enforce_client_limit

bp = Blueprint("geocode", __name__)

MAX_LOCATION_CHARS = 200
MIN_ELAPSED_HOURS = 0.1
MAX_ELAPSED_HOURS = 72.0


def _parse_body() -> tuple[str, float, str]:
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ApiError(400, "EMPTY_LOCATION", "Send a JSON object with location_text.")

    raw_location = body.get("location_text")
    if not isinstance(raw_location, str) or not raw_location.strip():
        raise ApiError(400, "EMPTY_LOCATION", "location_text is required.")
    location_text = raw_location.strip()
    if len(location_text) > MAX_LOCATION_CHARS:
        raise ApiError(
            400,
            "LOCATION_TOO_LONG",
            f"location_text must be at most {MAX_LOCATION_CHARS} characters.",
        )

    raw_hours = body.get("elapsed_hours")
    try:
        elapsed_hours = float(raw_hours)
    except (TypeError, ValueError):
        raise ApiError(
            400,
            "INVALID_ELAPSED_HOURS",
            f"elapsed_hours must be a number between {MIN_ELAPSED_HOURS} and {MAX_ELAPSED_HOURS}.",
        )
    if not MIN_ELAPSED_HOURS <= elapsed_hours <= MAX_ELAPSED_HOURS:
        raise ApiError(
            400,
            "INVALID_ELAPSED_HOURS",
            f"elapsed_hours must be between {MIN_ELAPSED_HOURS} and {MAX_ELAPSED_HOURS}.",
        )

    category = body.get("category")
    if not isinstance(category, str) or category not in CATEGORIES:
        allowed = ", ".join(CATEGORIES)
        raise ApiError(
            400,
            "UNKNOWN_CATEGORY",
            f"category must be one of: {allowed}.",
        )

    return location_text, elapsed_hours, category


@bp.post("/api/geocode")
def geocode():
    enforce_client_limit("geocode")
    location_text, elapsed_hours, category = _parse_body()
    try:
        lat, lng, formatted = geocode_address(location_text)
    except GeocodeProviderError as exc:
        raise ApiError(
            exc.status, exc.code, exc.message, retry_after=exc.retry_after
        ) from None

    return jsonify(
        {
            "lat": lat,
            "lng": lng,
            "formatted_address": formatted,
            "radius_m": radius_m(category, elapsed_hours),
            "category": category,
            "elapsed_hours": elapsed_hours,
            "lpb_note": LPB_NOTE,
        }
    )
