"""Collapse duplicate detections produced by overlapping tiles (pure numpy NMS)."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from detection.types import Detection

DEFAULT_IOU_THRESHOLD = 0.45

# A person on a tile seam is cropped in one tile and whole in the other, so the two
# boxes can share a low IoU while clearly being the same candidate. Suppressing on
# intersection-over-smaller-area as well catches that case.
DEFAULT_CONTAINMENT_THRESHOLD = 0.7


def _as_arrays(detections: Sequence[Detection]) -> tuple[np.ndarray, np.ndarray]:
    boxes = np.asarray([d.bbox_xyxy for d in detections], dtype=np.float64).reshape(-1, 4)
    scores = np.asarray([d.confidence for d in detections], dtype=np.float64)
    return boxes, scores


def _areas(boxes: np.ndarray) -> np.ndarray:
    return np.clip(boxes[:, 2] - boxes[:, 0], 0, None) * np.clip(boxes[:, 3] - boxes[:, 1], 0, None)


def _overlaps(box: np.ndarray, others: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return (IoU, intersection-over-smaller-area) of one box against many."""
    ix1 = np.maximum(box[0], others[:, 0])
    iy1 = np.maximum(box[1], others[:, 1])
    ix2 = np.minimum(box[2], others[:, 2])
    iy2 = np.minimum(box[3], others[:, 3])
    inter = np.clip(ix2 - ix1, 0, None) * np.clip(iy2 - iy1, 0, None)

    area = _areas(box.reshape(1, 4))[0]
    areas = _areas(others)

    union = np.maximum(area + areas - inter, 1e-9)
    smaller = np.maximum(np.minimum(area, areas), 1e-9)
    return inter / union, inter / smaller


def merge_detections(
    detections: Sequence[Detection],
    iou_threshold: float = DEFAULT_IOU_THRESHOLD,
    containment_threshold: float = DEFAULT_CONTAINMENT_THRESHOLD,
) -> list[Detection]:
    """Greedy NMS keeping the highest-confidence box of each cluster.

    The survivor's box is widened to the union of any absorbed box that is at least as
    large as it. Without that, a tile seam that cuts a person in half often leaves the
    clipped fragment as the winner (it can outscore the complete view), so the overlay
    would draw half a person. Confidence is always the survivor's own score — never
    averaged or boosted.

    Returns a new list sorted by confidence descending; the input is untouched.
    """
    if len(detections) < 2:
        return list(detections)

    boxes, scores = _as_arrays(detections)
    order = np.argsort(-scores, kind="stable")

    merged: list[Detection] = []
    while order.size:
        index = int(order[0])
        box = boxes[index].copy()
        pool = order[1:]

        while pool.size:
            iou, containment = _overlaps(box, boxes[pool])
            absorbed = (iou > iou_threshold) | (containment > containment_threshold)
            if not absorbed.any():
                break
            candidates = boxes[pool[absorbed]]
            more_complete = candidates[_areas(candidates) >= _areas(box.reshape(1, 4))[0]]
            pool = pool[~absorbed]
            if not len(more_complete):
                break
            box = np.array(
                [
                    min(box[0], more_complete[:, 0].min()),
                    min(box[1], more_complete[:, 1].min()),
                    max(box[2], more_complete[:, 2].max()),
                    max(box[3], more_complete[:, 3].max()),
                ]
            )
            # The widened box may now overlap fragments it previously missed.

        original = detections[index]
        bbox = [int(round(float(v))) for v in box]
        merged.append(
            original
            if bbox == list(original.bbox_xyxy)
            else Detection(
                bbox_xyxy=bbox,
                confidence=original.confidence,
                class_name=original.class_name,
            )
        )
        order = pool

    return merged
