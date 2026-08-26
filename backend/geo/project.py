"""Project pixel coordinates into WGS84 for a georeferenced demo image.

Assumes a nadir photo, constant ground sample distance, and a heading measured
clockwise from north. Fine for placing demo pins; not a photogrammetric model.
"""

from __future__ import annotations

import math
from typing import Any

METERS_PER_DEG_LAT = 111_320.0


def _as_geo(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    try:
        lat = float(raw["center_lat"])
        lng = float(raw["center_lng"])
    except (KeyError, TypeError, ValueError):
        return None
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0):
        return None
    try:
        gsd_m = float(raw.get("gsd_m", 0.15))
    except (TypeError, ValueError):
        return None
    if gsd_m <= 0:
        return None
    try:
        heading_deg = float(raw.get("heading_deg", 0.0))
    except (TypeError, ValueError):
        heading_deg = 0.0
    return {
        "center_lat": lat,
        "center_lng": lng,
        "gsd_m": gsd_m,
        "heading_deg": heading_deg,
        "demo_placement": bool(raw.get("demo_placement", False)),
    }


def geo_from_entry(entry: dict | None) -> dict[str, Any] | None:
    if not entry:
        return None
    return _as_geo(entry.get("geo"))


def public_geo(entry: dict | None) -> dict[str, Any] | None:
    """Fields the samples list may expose — no GSD/heading internals required."""
    geo = geo_from_entry(entry)
    if geo is None:
        return None
    return {
        "center_lat": geo["center_lat"],
        "center_lng": geo["center_lng"],
        "demo_placement": geo["demo_placement"],
    }


def meta_geo(entry: dict | None) -> dict[str, Any] | None:
    geo = geo_from_entry(entry)
    if geo is None:
        return None
    return {
        "center_lat": geo["center_lat"],
        "center_lng": geo["center_lng"],
        "gsd_m": geo["gsd_m"],
        "heading_deg": geo["heading_deg"],
        "demo_placement": geo["demo_placement"],
    }


def pixel_to_latlng(
    x: float,
    y: float,
    image_width: int,
    image_height: int,
    geo: dict[str, Any],
) -> tuple[float, float]:
    cx = image_width / 2.0
    cy = image_height / 2.0
    gsd = float(geo["gsd_m"])
    heading = math.radians(float(geo.get("heading_deg", 0.0)))
    east = (x - cx) * gsd
    north = (cy - y) * gsd
    east_r = east * math.cos(heading) + north * math.sin(heading)
    north_r = -east * math.sin(heading) + north * math.cos(heading)
    lat0 = float(geo["center_lat"])
    lng0 = float(geo["center_lng"])
    dlat = north_r / METERS_PER_DEG_LAT
    cos_lat = math.cos(math.radians(lat0))
    meters_per_deg_lng = METERS_PER_DEG_LAT * max(abs(cos_lat), 1e-6)
    dlng = east_r / meters_per_deg_lng
    return round(lat0 + dlat, 6), round(lng0 + dlng, 6)


def bbox_center_latlng(
    bbox_xyxy: list[int],
    image_width: int,
    image_height: int,
    geo: dict[str, Any],
) -> tuple[float, float]:
    x1, y1, x2, y2 = bbox_xyxy
    return pixel_to_latlng(
        (x1 + x2) / 2.0,
        (y1 + y2) / 2.0,
        image_width,
        image_height,
        geo,
    )


def apply_geo(
    detections: list[dict[str, Any]],
    image_width: int,
    image_height: int,
    geo: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Fill lat/lng on an already-shaped detections payload. No-op when geo is None."""
    if geo is None:
        return detections
    for item in detections:
        lat, lng = bbox_center_latlng(item["bbox_xyxy"], image_width, image_height, geo)
        item["lat"] = lat
        item["lng"] = lng
    return detections
