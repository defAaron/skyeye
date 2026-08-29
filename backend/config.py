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

VERSION = "0.3.0"

load_dotenv(BACKEND_DIR / ".env", override=True)


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


def _bool(name: str, default: bool) -> bool:
    raw = (os.environ.get(name) or "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def parse_cors_origins(raw: str) -> tuple[str, ...]:
    """Split CORS_ORIGIN on commas. Empty pieces are dropped."""
    return tuple(part.strip() for part in raw.split(",") if part.strip())


@dataclass(frozen=True)
class Settings:
    port: int = field(default_factory=lambda: _int("FLASK_PORT", 5001))
    cors_origin: str = field(
        default_factory=lambda: os.environ.get("CORS_ORIGIN", "http://localhost:5173")
    )
    cors_origin_regex: str = field(
        default_factory=lambda: (os.environ.get("CORS_ORIGIN_REGEX") or "").strip()
    )
    trust_proxy: bool = field(default_factory=lambda: _bool("TRUST_PROXY", False))
    weights: str = field(default_factory=lambda: os.environ.get("YOLO_WEIGHTS", "yolov8n.pt"))
    device: str = field(default_factory=lambda: os.environ.get("YOLO_DEVICE", "cpu"))
    conf_threshold: float = field(default_factory=lambda: _float("CONF_THRESHOLD", 0.25))
    tile_size: int = field(default_factory=lambda: _int("TILE_SIZE", 640))
    tile_overlap: float = field(default_factory=lambda: _float("TILE_OVERLAP", 0.2))
    tile_batch_size: int = field(default_factory=lambda: _int("TILE_BATCH_SIZE", 1))
    torch_num_threads: int = field(default_factory=lambda: _int("TORCH_NUM_THREADS", 1))
    max_upload_bytes: int = field(default_factory=lambda: _int("MAX_UPLOAD_BYTES", 25 * 1024 * 1024))
    max_image_pixels: int = field(default_factory=lambda: _int("MAX_IMAGE_PIXELS", 40_000_000))

    allowed_mime_types: tuple[str, ...] = ("image/jpeg", "image/png")
    google_maps_api_key: str = field(
        default_factory=lambda: (os.environ.get("GOOGLE_MAPS_API_KEY") or "").strip()
    )
    gemini_api_key: str = field(
        default_factory=lambda: (os.environ.get("GEMINI_API_KEY") or "").strip()
    )
    groq_api_key: str = field(
        default_factory=lambda: (os.environ.get("GROQ_API_KEY") or "").strip()
    )

    # Stay under typical Gemini free-tier RPM/RPD so a tight UI loop cannot
    # burn the key. Defaults are conservative vs ~10–15 RPM / ~250–1500 RPD.
    gemini_max_rpm: int = field(default_factory=lambda: _int("GEMINI_MAX_RPM", 8))
    gemini_max_rpd: int = field(default_factory=lambda: _int("GEMINI_MAX_RPD", 200))
    gemini_cooldown_seconds: int = field(
        default_factory=lambda: _int("GEMINI_COOLDOWN_SECONDS", 60)
    )
    groq_max_rpm: int = field(default_factory=lambda: _int("GROQ_MAX_RPM", 20))
    groq_max_rpd: int = field(default_factory=lambda: _int("GROQ_MAX_RPD", 500))
    groq_cooldown_seconds: int = field(
        default_factory=lambda: _int("GROQ_COOLDOWN_SECONDS", 30)
    )
    geocode_max_rpm: int = field(default_factory=lambda: _int("GEOCODE_MAX_RPM", 20))
    geocode_max_rpd: int = field(default_factory=lambda: _int("GEOCODE_MAX_RPD", 400))
    geocode_cooldown_seconds: int = field(
        default_factory=lambda: _int("GEOCODE_COOLDOWN_SECONDS", 60)
    )
    extract_ip_per_minute: int = field(
        default_factory=lambda: _int("EXTRACT_IP_PER_MINUTE", 8)
    )
    extract_ip_per_day: int = field(default_factory=lambda: _int("EXTRACT_IP_PER_DAY", 20))
    geocode_ip_per_minute: int = field(
        default_factory=lambda: _int("GEOCODE_IP_PER_MINUTE", 10)
    )
    geocode_ip_per_day: int = field(default_factory=lambda: _int("GEOCODE_IP_PER_DAY", 80))
    detect_ip_per_minute: int = field(
        default_factory=lambda: _int("DETECT_IP_PER_MINUTE", 20)
    )
    detect_ip_per_day: int = field(default_factory=lambda: _int("DETECT_IP_PER_DAY", 80))

    @property
    def cors_origins(self) -> tuple[str, ...]:
        return parse_cors_origins(self.cors_origin)

    @property
    def geocode_configured(self) -> bool:
        return bool(self.google_maps_api_key)

    @property
    def gemini_configured(self) -> bool:
        return bool(self.gemini_api_key)

    @property
    def groq_configured(self) -> bool:
        return bool(self.groq_api_key)

    @property
    def extract_configured(self) -> bool:
        return self.gemini_configured or self.groq_configured

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
