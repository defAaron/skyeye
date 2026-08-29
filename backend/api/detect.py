from __future__ import annotations

import io
import time

from flask import Blueprint, current_app, jsonify, request
from PIL import Image, UnidentifiedImageError

from api.errors import ApiError
from api.samples import find_sample, sample_image_path
from config import DISCLAIMER, settings
from geo.project import apply_geo, meta_geo
from ratelimit import enforce_client_limit

bp = Blueprint("detect", __name__)

_PIL_FORMAT_TO_MIME = {"JPEG": "image/jpeg", "PNG": "image/png"}


def _parse_conf() -> float:
    raw = request.form.get("conf")
    if raw is None or raw == "":
        return settings.conf_threshold
    try:
        value = float(raw)
    except ValueError:
        raise ApiError(400, "INVALID_CONF", "conf must be a number between 0.01 and 0.95.")
    if not 0.01 <= value <= 0.95:
        raise ApiError(400, "INVALID_CONF", "conf must be between 0.01 and 0.95.")
    return value


def _open_image(data: bytes) -> Image.Image:
    """Validate from the header first, decode second.

    Order matters: a small file can declare a huge canvas, so the pixel cap has to be
    enforced before any decode allocates buffers for it.
    """
    try:
        # Pillow runs its own bomb check here, from the header, before any decode.
        image = Image.open(io.BytesIO(data))
    except Image.DecompressionBombError:
        raise _too_large()
    except (UnidentifiedImageError, OSError):
        raise ApiError(400, "INVALID_IMAGE", "The file could not be decoded as an image.")

    if _PIL_FORMAT_TO_MIME.get(image.format or "") not in settings.allowed_mime_types:
        raise ApiError(400, "UNSUPPORTED_TYPE", "Only JPEG and PNG images are supported.")

    if image.width * image.height > settings.max_image_pixels:
        raise _too_large()

    try:
        image.load()
    except Image.DecompressionBombError:
        raise _too_large()
    except (UnidentifiedImageError, OSError):
        raise ApiError(400, "INVALID_IMAGE", "The file could not be decoded as an image.")

    return image.convert("RGB")


def _too_large() -> ApiError:
    limit_mp = settings.max_image_pixels // 1_000_000
    return ApiError(413, "IMAGE_TOO_LARGE", f"Image exceeds the {limit_mp} megapixel limit.")


def _resolve_input() -> tuple[Image.Image, str, str | None, dict | None]:
    upload = request.files.get("image")
    sample_id = (request.form.get("sample_id") or "").strip()

    if upload is not None and upload.filename and sample_id:
        raise ApiError(400, "AMBIGUOUS_INPUT", "Provide either an image upload or a sample_id.")

    if upload is not None and upload.filename:
        data = upload.read()
        if not data:
            raise ApiError(400, "INVALID_IMAGE", "The uploaded file is empty.")
        if len(data) > settings.max_upload_bytes:
            raise ApiError(413, "FILE_TOO_LARGE", "Upload exceeds the maximum allowed size.")
        return _open_image(data), "upload", None, None

    if sample_id:
        entry = find_sample(sample_id)
        path = sample_image_path(entry)
        return _open_image(path.read_bytes()), "sample", entry["id"], entry

    raise ApiError(400, "NO_IMAGE", "Provide an image upload or a sample_id.")


@bp.post("/api/detect")
def detect():
    enforce_client_limit("detect")
    started = time.perf_counter()
    image, source, sample_id, sample_entry = _resolve_input()
    conf = _parse_conf()

    from detection.infer import detect_image, detections_payload

    detections, tiles = detect_image(image, conf=conf)
    geo = meta_geo(sample_entry) if source == "sample" else None
    payload = apply_geo(detections_payload(detections), image.width, image.height, geo)

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    current_app.logger.info(
        "detect source=%s sample=%s size=%dx%d tiles=%d hits=%d conf=%.2f geo=%s %dms",
        source,
        sample_id or "-",
        image.width,
        image.height,
        tiles,
        len(detections),
        conf,
        "yes" if geo else "no",
        elapsed_ms,
    )

    return jsonify(
        {
            "image_width": image.width,
            "image_height": image.height,
            "detections": payload,
            "meta": {
                "source": source,
                "sample_id": sample_id,
                "tiles": tiles,
                "conf_threshold": conf,
                "inference_ms": elapsed_ms,
                "model": settings.weights_label,
                "geo": geo,
            },
            "disclaimer": DISCLAIMER,
        }
    )
