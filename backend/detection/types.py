from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Detection:
    """One candidate, in pixel space on the full submitted image."""

    bbox_xyxy: list[int]
    confidence: float
    class_name: str = "person"

    def area(self) -> int:
        x1, y1, x2, y2 = self.bbox_xyxy
        return max(0, x2 - x1) * max(0, y2 - y1)
