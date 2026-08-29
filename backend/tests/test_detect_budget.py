"""Detect working-resolution budget. Does not load YOLO."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

from PIL import Image

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from config import settings  # noqa: E402
from detection.infer import _detections_to_original, _fit_for_detect  # noqa: E402
from detection.tiling import tile_count  # noqa: E402
from detection.types import Detection  # noqa: E402


class FitForDetectTests(unittest.TestCase):
    def test_small_image_is_unchanged(self) -> None:
        image = Image.new("RGB", (640, 480), color=(8, 8, 8))
        work, orig_w, orig_h = _fit_for_detect(image)
        self.assertIs(work, image)
        self.assertEqual((orig_w, orig_h), (640, 480))

    def test_lawn_fixture_size_stays_under_tile_budget(self) -> None:
        image = Image.new("RGB", (3652, 2737), color=(8, 8, 8))
        work, orig_w, orig_h = _fit_for_detect(image)
        self.assertEqual((orig_w, orig_h), (3652, 2737))
        self.assertLessEqual(work.width * work.height, settings.detect_max_pixels + 2_000)
        self.assertLessEqual(tile_count(work.width, work.height), 16)


class BoxScaleTests(unittest.TestCase):
    def test_identity_when_sizes_match(self) -> None:
        detections = [Detection(bbox_xyxy=[10, 20, 30, 40], confidence=0.9)]
        self.assertEqual(
            _detections_to_original(detections, 100, 80, 100, 80)[0].bbox_xyxy,
            [10, 20, 30, 40],
        )

    def test_maps_boxes_back_to_original_pixels(self) -> None:
        detections = [Detection(bbox_xyxy=[10, 10, 20, 20], confidence=0.8)]
        scaled = _detections_to_original(detections, 100, 100, 200, 200)
        self.assertEqual(scaled[0].bbox_xyxy, [20, 20, 40, 40])
        self.assertEqual(scaled[0].confidence, 0.8)


if __name__ == "__main__":
    unittest.main()
