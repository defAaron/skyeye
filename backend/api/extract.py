from __future__ import annotations

from flask import Blueprint, jsonify, request

from api.errors import ApiError
from extract.providers import ExtractProviderError, extract_report
from ratelimit import enforce_client_limit

bp = Blueprint("extract", __name__)

MAX_REPORT_CHARS = 4000


def _parse_body() -> str:
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ApiError(400, "EMPTY_REPORT", "Send a JSON object with report_text.")

    raw = body.get("report_text")
    if not isinstance(raw, str) or not raw.strip():
        raise ApiError(400, "EMPTY_REPORT", "report_text is required.")
    report_text = raw.strip()
    if len(report_text) > MAX_REPORT_CHARS:
        raise ApiError(
            400,
            "REPORT_TOO_LONG",
            f"report_text must be at most {MAX_REPORT_CHARS} characters.",
        )
    return report_text


@bp.post("/api/extract")
def extract():
    enforce_client_limit("extract")
    report_text = _parse_body()
    try:
        payload = extract_report(report_text)
    except ExtractProviderError as exc:
        raise ApiError(
            exc.status, exc.code, exc.message, retry_after=exc.retry_after
        ) from None
    return jsonify(payload)
