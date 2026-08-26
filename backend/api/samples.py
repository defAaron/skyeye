from __future__ import annotations

import json
from functools import lru_cache

from flask import Blueprint, jsonify, send_file

from api.errors import ApiError
from config import FIXTURE_IMAGES_DIR, MANIFEST_PATH
from geo.project import public_geo

bp = Blueprint("samples", __name__)

_MIME_BY_SUFFIX = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}


@lru_cache(maxsize=1)
def load_manifest() -> list[dict]:
    if not MANIFEST_PATH.exists():
        return []
    with MANIFEST_PATH.open(encoding="utf-8") as handle:
        data = json.load(handle)
    return data.get("samples", [])


def find_sample(sample_id: str) -> dict:
    """Look up by manifest id only; user input is never joined into a path."""
    for entry in load_manifest():
        if entry.get("id") == sample_id:
            return entry
    raise ApiError(404, "SAMPLE_NOT_FOUND", "No demo sample with that id.")


def sample_image_path(entry: dict):
    path = (FIXTURE_IMAGES_DIR / entry["filename"]).resolve()
    if not path.is_file() or FIXTURE_IMAGES_DIR.resolve() not in path.parents:
        raise ApiError(404, "SAMPLE_NOT_FOUND", "Demo image is not available locally.")
    return path


def _public_fields(entry: dict) -> dict:
    return {
        "id": entry["id"],
        "label": entry.get("label", entry["id"]),
        "scenario": entry.get("scenario", "unspecified"),
        "width": entry.get("width"),
        "height": entry.get("height"),
        "terrain": entry.get("terrain"),
        "source": entry.get("source"),
        "source_url": entry.get("source_url"),
        "license": entry.get("license"),
        "attribution": entry.get("attribution"),
        "expected_min_detections": entry.get("expected_min_detections", 0),
        "image_url": f"/api/samples/{entry['id']}/image",
        "geo": public_geo(entry),
    }


@bp.get("/api/samples")
def list_samples():
    available = [
        _public_fields(entry)
        for entry in load_manifest()
        if (FIXTURE_IMAGES_DIR / entry.get("filename", "")).is_file()
    ]
    return jsonify({"samples": available})


@bp.get("/api/samples/<sample_id>/image")
def sample_image(sample_id: str):
    entry = find_sample(sample_id)
    path = sample_image_path(entry)
    mimetype = _MIME_BY_SUFFIX.get(path.suffix.lower(), "application/octet-stream")
    return send_file(path, mimetype=mimetype)
