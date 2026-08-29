"""Inference entrypoints: full-image pass, tiled pass, and a JSON CLI."""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
import threading
import time
from collections.abc import Iterable, Iterator, Sequence
from typing import Any

from PIL import Image

from config import DISCLAIMER, settings
from detection.merge import merge_detections
from detection.model import PERSON_CLASS_NAME, get_model
from detection.tiling import Tile, iter_tiles, project_box, tile_grid
from detection.types import Detection

logger = logging.getLogger(__name__)

# One detect at a time. Concurrent YOLO forwards on gthread workers double RSS
# and are the usual status-137 on a 2 GB Render box.
_infer_lock = threading.RLock()

# One tile per ONNX run keeps peak RSS low. The 2.5 MP working-resolution cap
# is what keeps tile count inside the 180s client budget.
MAX_TILE_BATCH_SIZE = 8

# YOLOv8's native input size.
MODEL_IMGSZ = 640


def _tile_batch_size() -> int:
    return max(1, min(MAX_TILE_BATCH_SIZE, int(settings.tile_batch_size)))


def _fit_for_detect(image: Image.Image) -> tuple[Image.Image, int, int]:
    """Downscale huge aerials so the tile grid can finish inside the request budget.

    Boxes are projected back to the original pixel space before the response.
    """
    orig_w, orig_h = image.width, image.height
    budget = max(MODEL_IMGSZ * MODEL_IMGSZ, int(settings.detect_max_pixels))
    pixels = orig_w * orig_h
    if pixels <= budget:
        return image, orig_w, orig_h
    scale = math.sqrt(budget / pixels)
    width = max(1, int(round(orig_w * scale)))
    height = max(1, int(round(orig_h * scale)))
    return image.resize((width, height), Image.Resampling.BILINEAR), orig_w, orig_h


def _detections_to_original(
    detections: list[Detection],
    src_w: int,
    src_h: int,
    orig_w: int,
    orig_h: int,
) -> list[Detection]:
    if src_w == orig_w and src_h == orig_h:
        return detections
    sx = orig_w / src_w
    sy = orig_h / src_h
    scaled: list[Detection] = []
    for detection in detections:
        x1, y1, x2, y2 = detection.bbox_xyxy
        scaled.append(
            Detection(
                bbox_xyxy=project_box([x1 * sx, y1 * sy, x2 * sx, y2 * sy], 0, 0, orig_w, orig_h),
                confidence=detection.confidence,
                class_name=detection.class_name,
            )
        )
    return scaled


def _project_local(
    detections: Sequence[Detection],
    offset_x: int,
    offset_y: int,
    width: int,
    height: int,
) -> list[Detection]:
    out: list[Detection] = []
    for detection in detections:
        bbox = project_box(detection.bbox_xyxy, offset_x, offset_y, width, height)
        if bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
            continue
        out.append(
            Detection(
                bbox_xyxy=bbox,
                confidence=detection.confidence,
                class_name=PERSON_CLASS_NAME,
            )
        )
    return out


def _sorted_desc(detections: list[Detection]) -> list[Detection]:
    return sorted(detections, key=lambda d: d.confidence, reverse=True)


def _as_rgb(image: Image.Image) -> Image.Image:
    return image if image.mode == "RGB" else image.convert("RGB")


def _batched(tiles: Iterator[Tile], size: int) -> Iterable[list[Tile]]:
    batch: list[Tile] = []
    for tile in tiles:
        batch.append(tile)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def detect_full_image(image: Image.Image, conf: float) -> list[Detection]:
    """One model pass over the whole image, no tiling.

    Fast, but a large aerial is letterboxed down to the network input size, which
    shrinks distant people below what the detector can see. Use `detect_image` for those.
    """
    with _infer_lock:
        image = _as_rgb(image)
        model = get_model()
        return _sorted_desc(_project_local(model.infer(image, conf), 0, 0, image.width, image.height))


def detect_image(image: Image.Image, conf: float) -> tuple[list[Detection], int]:
    """Return (detections sorted by confidence desc, tile count).

    Tiles the image at `settings.tile_size` / `settings.tile_overlap`, projects each
    tile's boxes into full-image pixels, then merges duplicates across seams. Images
    smaller than one tile take the single-pass path and report one tile.

    Callers are expected to have already enforced `settings.max_image_pixels`.
    """
    with _infer_lock:
        image = _as_rgb(image)
        work, orig_w, orig_h = _fit_for_detect(image)
        grid = tile_grid(work.width, work.height)
        tiles = len(grid)

        if tiles <= 1:
            detections = detect_full_image(work, conf)
            return (
                _detections_to_original(detections, work.width, work.height, orig_w, orig_h),
                max(tiles, 1),
            )

        model = get_model()
        raw: list[Detection] = []
        for batch in _batched(iter_tiles(work), _tile_batch_size()):
            for tile in batch:
                raw.extend(
                    _project_local(
                        model.infer(tile.image, conf),
                        tile.offset_x,
                        tile.offset_y,
                        work.width,
                        work.height,
                    )
                )

        merged = _sorted_desc(
            _detections_to_original(
                merge_detections(raw), work.width, work.height, orig_w, orig_h
            )
        )
        logger.info(
            "tiled detect %dx%d work=%dx%d tiles=%d raw=%d merged=%d conf=%.2f",
            orig_w,
            orig_h,
            work.width,
            work.height,
            tiles,
            len(raw),
            len(merged),
            conf,
        )
        return merged, tiles


def detections_payload(detections: Sequence[Detection]) -> list[dict[str, Any]]:
    """Detection objects in the shape frozen by docs/api-contract.md."""
    return [
        {
            "id": f"d{index}",
            "bbox_xyxy": detection.bbox_xyxy,
            "confidence": round(detection.confidence, 4),
            "class_name": detection.class_name,
            "lat": None,
            "lng": None,
        }
        for index, detection in enumerate(detections, start=1)
    ]


def _cli(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m detection.infer",
        description="Run person detection on one image and print JSON.",
    )
    parser.add_argument("image", help="path to a JPEG or PNG image")
    parser.add_argument(
        "--conf",
        type=float,
        default=settings.conf_threshold,
        help=f"confidence floor (default {settings.conf_threshold})",
    )
    parser.add_argument(
        "--no-tiling",
        action="store_true",
        help="single downscaled pass over the whole image instead of tiling",
    )
    args = parser.parse_args(argv)

    try:
        with Image.open(args.image) as handle:
            image = _as_rgb(handle)
            image.load()
    except (OSError, ValueError) as exc:
        print(f"could not read image: {exc}", file=sys.stderr)
        return 2

    started = time.perf_counter()
    if args.no_tiling:
        detections = detect_full_image(image, conf=args.conf)
        tiles = 1
    else:
        detections, tiles = detect_image(image, conf=args.conf)
    elapsed_ms = int((time.perf_counter() - started) * 1000)

    print(
        json.dumps(
            {
                "image_width": image.width,
                "image_height": image.height,
                "detections": detections_payload(detections),
                "meta": {
                    "source": "cli",
                    "sample_id": None,
                    "tiles": tiles,
                    "conf_threshold": args.conf,
                    "inference_ms": elapsed_ms,
                    "model": settings.weights_label,
                    "geo": None,
                },
                "disclaimer": DISCLAIMER,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
