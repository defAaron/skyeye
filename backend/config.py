"""Env-backed settings. Defaults match docs/api-contract.md."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = BACKEND_DIR / "fixtures"
FIXTURE_IMAGES_DIR = FIXTURES_DIR / "images"
MANIFEST_PATH = FIXTURES_DIR / "manifest.json"

VERSION = "0.2.0"

load_dotenv(BACKEND_DIR / ".env")


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    port: int = field(default_factory=lambda: _int("FLASK_PORT", 5001))
    cors_origin: str = field(
        default_factory=lambda: os.environ.get("CORS_ORIGIN", "http://localhost:5173")
    )
    weights: str = field(default_factory=lambda: os.environ.get("YOLO_WEIGHTS", "yolov8n.pt"))
    device: str = field(default_factory=lambda: os.environ.get("YOLO_DEVICE", "cpu"))
    conf_threshold: float = field(default_factory=lambda: _float("CONF_THRESHOLD", 0.25))
    tile_size: int = field(default_factory=lambda: _int("TILE_SIZE", 640))
    tile_overlap: float = field(default_factory=lambda: _float("TILE_OVERLAP", 0.2))
    max_upload_bytes: int = field(default_factory=lambda: _int("MAX_UPLOAD_BYTES", 25 * 1024 * 1024))
    max_image_pixels: int = field(default_factory=lambda: _int("MAX_IMAGE_PIXELS", 40_000_000))

    allowed_mime_types: tuple[str, ...] = ("image/jpeg", "image/png")
    google_maps_api_key: str = field(
        default_factory=lambda: (os.environ.get("GOOGLE_MAPS_API_KEY") or "").strip()
    )

    @property
    def geocode_configured(self) -> bool:
        return bool(self.google_maps_api_key)

    @property
    def weights_label(self) -> str:
        """Basename only — an absolute YOLO_WEIGHTS path must not leak to API clients."""
        return Path(self.weights).name

    def limits_payload(self) -> dict:
        return {
            "max_upload_bytes": self.max_upload_bytes,
            "max_image_pixels": self.max_image_pixels,
            "allowed_types": list(self.allowed_mime_types),
        }


settings = Settings()

DISCLAIMER = (
    "SkyEye surfaces possible leads only. It does not confirm a person's location "
    "or safety. Contact 911 / local SAR immediately."
)
