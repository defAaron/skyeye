"""Sliding-window tiling for large aerials, plus box projection back to full-image space.

Aerial people are only a few dozen pixels tall, so a single downscaled pass loses them.
The grid keeps every tile at native resolution and overlaps neighbours so a person
straddling a seam is fully visible in at least one tile.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Sequence

from PIL import Image

from config import settings

MIN_TILE_SIZE = 32
MAX_OVERLAP = 0.9


@dataclass(frozen=True)
class Tile:
    """One crop of the source image plus its top-left offset in full-image pixels."""

    image: Image.Image
    offset_x: int
    offset_y: int


def _resolve(tile_size: int | None, overlap: float | None) -> tuple[int, int]:
    size = max(MIN_TILE_SIZE, int(settings.tile_size if tile_size is None else tile_size))
    frac = settings.tile_overlap if overlap is None else overlap
    frac = min(max(float(frac), 0.0), MAX_OVERLAP)
    stride = max(1, int(round(size * (1.0 - frac))))
    return size, stride


def _starts(extent: int, size: int, stride: int) -> list[int]:
    """Window origins along one axis, always including the flush-to-edge window."""
    if extent <= size:
        return [0]
    positions = list(range(0, extent - size + 1, stride))
    last = extent - size
    if positions[-1] != last:
        positions.append(last)
    return positions


def tile_grid(
    width: int,
    height: int,
    tile_size: int | None = None,
    overlap: float | None = None,
) -> list[tuple[int, int, int, int]]:
    """Tile boxes as `(x1, y1, x2, y2)`, row-major, clipped to the image.

    An image smaller than one tile yields exactly one box covering it: tiles are never
    upscaled to fill the window.
    """
    size, stride = _resolve(tile_size, overlap)
    return [
        (x, y, min(x + size, width), min(y + size, height))
        for y in _starts(height, size, stride)
        for x in _starts(width, size, stride)
    ]


def tile_count(
    width: int,
    height: int,
    tile_size: int | None = None,
    overlap: float | None = None,
) -> int:
    return len(tile_grid(width, height, tile_size, overlap))


def iter_tiles(
    image: Image.Image,
    tile_size: int | None = None,
    overlap: float | None = None,
) -> Iterator[Tile]:
    """Crop tiles lazily so callers never hold the whole grid in memory at once."""
    for x1, y1, x2, y2 in tile_grid(image.width, image.height, tile_size, overlap):
        yield Tile(image=image.crop((x1, y1, x2, y2)), offset_x=x1, offset_y=y1)


def project_box(
    box: Sequence[float],
    offset_x: int,
    offset_y: int,
    width: int,
    height: int,
) -> list[int]:
    """Shift a tile-local xyxy box into full-image integer pixels, clamped to bounds."""
    x1, y1, x2, y2 = (float(v) for v in box[:4])
    px1 = min(max(int(round(x1 + offset_x)), 0), width)
    py1 = min(max(int(round(y1 + offset_y)), 0), height)
    px2 = min(max(int(round(x2 + offset_x)), 0), width)
    py2 = min(max(int(round(y2 + offset_y)), 0), height)
    if px2 < px1:
        px1, px2 = px2, px1
    if py2 < py1:
        py1, py2 = py2, py1
    return [px1, py1, px2, py2]
