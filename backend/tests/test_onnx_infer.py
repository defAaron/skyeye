"""ONNX YOLO post-process. No Runtime session required."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from detection.onnx_infer import (  # noqa: E402
    detections_from_output,
    nms,
    parse_yolo_output,
    xywh_to_xyxy,
)


class ParseTests(unittest.TestCase):
    def test_transposes_84_by_n(self) -> None:
        raw = np.zeros((1, 84, 3), dtype=np.float32)
        parsed = parse_yolo_output(raw)
        self.assertEqual(parsed.shape, (3, 84))


class BoxTests(unittest.TestCase):
    def test_xywh_center_to_xyxy(self) -> None:
        xyxy = xywh_to_xyxy(np.array([[10.0, 10.0, 4.0, 6.0]]))
        np.testing.assert_allclose(xyxy, [[8.0, 7.0, 12.0, 13.0]])

    def test_nms_keeps_higher_score(self) -> None:
        boxes = np.array(
            [
                [0.0, 0.0, 10.0, 10.0],
                [1.0, 1.0, 11.0, 11.0],
            ]
        )
        keep = nms(boxes, np.array([0.9, 0.4]), iou_threshold=0.3)
        self.assertEqual(keep, [0])


class DetectionFilterTests(unittest.TestCase):
    def test_drops_non_person_and_low_conf(self) -> None:
        # (1, 84, 2): first row is a person at 0.9, second is a car at 0.95.
        raw = np.zeros((1, 84, 2), dtype=np.float32)
        raw[0, 0:4, 0] = [20.0, 20.0, 8.0, 8.0]
        raw[0, 4, 0] = 0.9
        raw[0, 0:4, 1] = [40.0, 40.0, 8.0, 8.0]
        raw[0, 6, 1] = 0.95
        image = Image.new("RGB", (80, 80))
        detections = detections_from_output(raw, image, conf=0.25, scale=1.0, pad_x=0.0, pad_y=0.0)
        self.assertEqual(len(detections), 1)
        self.assertEqual(detections[0].class_name, "person")
        self.assertGreaterEqual(detections[0].confidence, 0.89)


if __name__ == "__main__":
    unittest.main()
