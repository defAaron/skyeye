"""Inference entrypoints: full-image pass, tiled pass, and a JSON CLI."""

from __future__ import annotations

import argparse
import gc
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
from detection.model import PERSON_CLASS_NAME, get_model, person_class_ids
from detection.tiling import Tile, iter_tiles, project_box, tile_grid
from detection.types import Detection

logger = logging.getLogger(__name__)

# One detect at a time. Concurrent YOLO forwards on gthread workers double RSS
# and are the usual status-137 on a 2 GB Render box.
_infer_lock = threading.RLock()

# Tiles per model call. Default 1 (see TILE_BATCH_SIZE) so a 2 GB instance
# does not hold eight 640px crops plus activations at once.
MAX_TILE_BATCH_SIZE = 8

# YOLOv8's native input size.
MODEL_IMGSZ = 640


def _tile_batch_size() -> int:
    return max(1, min(MAX_TILE_BATCH_SIZE, int(settings.tile_batch_size)))


def _infer_imgsz() -> int:
    """Model input size, deliberately decoupled from the tile size.

    A tile is never fed to the model smaller than the network's native size, so setting
    `TILE_SIZE` below 640 upscales each crop and makes small people bigger in network
    pixels (the usual small-object recall lever) instead of just shrinking the input.
    Tiles larger than that are kept at full detail rather than downscaled.
    """
    return int(math.ceil(max(MODEL_IMGSZ, int(settings.tile_size)) / 32) * 32)


def _target_class_ids(model) -> list[int]:
    """Class ids we are allowed to emit — person only."""
    ids = person_class_ids(model)
    if ids:
        return ids
    # A single-class aerial-person fine-tune may label its only class something other
    # than "person". Anything with more classes we refuse rather than risk emitting
    # non-person candidates.
    names = getattr(model, "names", {}) or {}
    if len(names) == 1:
        return [int(next(iter(names)))]
    return []


def _predict(model, images: Sequence[Image.Image], conf: float, class_ids: Sequence[int]):
    return model.predict(
        list(images),
        conf=conf,
        imgsz=_infer_imgsz(),
        device=settings.device,
        classes=list(class_ids),
        verbose=False,
    )


def _detections_from_result(
    result,
    allowed: set[int],
    offset_x: int,
    offset_y: int,
    width: int,
    height: int,
) -> list[Detection]:
    boxes = getattr(result, "boxes", None)
    if boxes is None or len(boxes) == 0:
        return []

    xyxy = boxes.xyxy.cpu().numpy()
    confs = boxes.conf.cpu().numpy()
    classes = boxes.cls.cpu().numpy().astype(int)

    out: list[Detection] = []
    for row, confidence, class_id in zip(xyxy, confs, classes):
        if int(class_id) not in allowed:
            continue
        bbox = project_box(row, offset_x, offset_y, width, height)
        if bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
            continue
        out.append(
            Detection(
                bbox_xyxy=bbox,
                confidence=float(confidence),
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
        class_ids = _target_class_ids(model)
        if not class_ids:
            logger.warning("weights %s expose no person class; returning no detections", settings.weights)
            return []

        results = _predict(model, [image], conf, class_ids)
        allowed = set(class_ids)
        detections: list[Detection] = []
        for result in results:
            detections.extend(
                _detections_from_result(result, allowed, 0, 0, image.width, image.height)
            )
        return _sorted_desc(detections)


def detect_image(image: Image.Image, conf: float) -> tuple[list[Detection], int]:
    """Return (detections sorted by confidence desc, tile count).

    Tiles the image at `settings.tile_size` / `settings.tile_overlap`, projects each
    tile's boxes into full-image pixels, then merges duplicates across seams. Images
    smaller than one tile take the single-pass path and report one tile.

    Callers are expected to have already enforced `settings.max_image_pixels`.
    """
    with _infer_lock:
        image = _as_rgb(image)
        grid = tile_grid(image.width, image.height)
        tiles = len(grid)

        if tiles <= 1:
            return detect_full_image(image, conf), max(tiles, 1)

        model = get_model()
        class_ids = _target_class_ids(model)
        if not class_ids:
            logger.warning("weights %s expose no person class; returning no detections", settings.weights)
            return [], tiles

        allowed = set(class_ids)
        raw: list[Detection] = []
        for batch in _batched(iter_tiles(image), _tile_batch_size()):
            results = _predict(model, [tile.image for tile in batch], conf, class_ids)
            for tile, result in zip(batch, results):
                raw.extend(
                    _detections_from_result(
                        result, allowed, tile.offset_x, tile.offset_y, image.width, image.height
                    )
                )
            del results, batch
            gc.collect()

        merged = _sorted_desc(merge_detections(raw))
        logger.info(
            "tiled detect %dx%d tiles=%d raw=%d merged=%d conf=%.2f",
            image.width,
            image.height,
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
