"""Single error shape for every API failure. Never leaks paths or stack traces."""

from __future__ import annotations

from flask import jsonify


class ApiError(Exception):
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


def error_response(status: int, code: str, message: str, retry_after: int | None = None):
    response = jsonify({"error": {"code": code, "message": message}})
    if retry_after is not None:
        response.headers["Retry-After"] = str(max(1, int(retry_after)))
    return response, status


def register_error_handlers(app) -> None:
    @app.errorhandler(ApiError)
    def _handle_api_error(exc: ApiError):
        return error_response(exc.status, exc.code, exc.message, exc.retry_after)

    @app.errorhandler(404)
    def _handle_404(_exc):
        return error_response(404, "NOT_FOUND", "Unknown endpoint.")

    @app.errorhandler(405)
    def _handle_405(_exc):
        return error_response(405, "METHOD_NOT_ALLOWED", "Method not allowed for this endpoint.")

    @app.errorhandler(413)
    def _handle_413(_exc):
        return error_response(413, "FILE_TOO_LARGE", "Upload exceeds the maximum allowed size.")

    @app.errorhandler(Exception)
    def _handle_unexpected(exc: Exception):
        app.logger.exception("Unhandled error: %s", exc)
        return error_response(500, "INTERNAL_ERROR", "Unexpected server error.")
