"""YOLOv8n ONNX post-process. No PyTorch import — that is what OOMs Render."""

from __future__ import annotations

import numpy as np
from PIL import Image

from detection.types import Detection

PERSON_CLASS_ID = 0
LETTERBOX_COLOR = (114, 114, 114)
NMS_IOU = 0.45


def letterbox(image: Image.Image, size: int) -> tuple[Image.Image, float, float, float]:
    """Resize with unchanged aspect ratio and pad to a square, Ultralytics-style."""
    width, height = image.size
    scale = min(size / width, size / height)
    new_w = max(1, int(round(width * scale)))
    new_h = max(1, int(round(height * scale)))
    pad_x = (size - new_w) / 2
    pad_y = (size - new_h) / 2
    resized = image.resize((new_w, new_h), Image.Resampling.BILINEAR)
    canvas = Image.new("RGB", (size, size), LETTERBOX_COLOR)
    canvas.paste(resized, (int(round(pad_x - 0.1)), int(round(pad_y - 0.1))))
    return canvas, scale, pad_x, pad_y


def image_to_nchw(image: Image.Image) -> np.ndarray:
    array = np.asarray(image, dtype=np.float32) / 255.0
    return np.transpose(array, (2, 0, 1))[None]


def parse_yolo_output(raw: np.ndarray) -> np.ndarray:
    """Return (N, 84) rows: xywh in letterbox pixels, then 80 class scores."""
    pred = np.asarray(raw)
    if pred.ndim == 3:
        pred = pred[0]
    if pred.shape[0] == 84 and pred.shape[1] != 84:
        pred = pred.T
    if pred.shape[-1] < 5:
        raise ValueError("unexpected YOLO ONNX output shape")
    return pred


def xywh_to_xyxy(xywh: np.ndarray) -> np.ndarray:
    x, y, w, h = xywh[:, 0], xywh[:, 1], xywh[:, 2], xywh[:, 3]
    return np.stack((x - w / 2, y - h / 2, x + w / 2, y + h / 2), axis=1)


def scale_boxes_to_image(
    xyxy: np.ndarray,
    scale: float,
    pad_x: float,
    pad_y: float,
    width: int,
    height: int,
) -> np.ndarray:
    boxes = xyxy.copy()
    boxes[:, [0, 2]] = (boxes[:, [0, 2]] - pad_x) / scale
    boxes[:, [1, 3]] = (boxes[:, [1, 3]] - pad_y) / scale
    boxes[:, 0] = np.clip(boxes[:, 0], 0, width)
    boxes[:, 1] = np.clip(boxes[:, 1], 0, height)
    boxes[:, 2] = np.clip(boxes[:, 2], 0, width)
    boxes[:, 3] = np.clip(boxes[:, 3], 0, height)
    return boxes


def nms(boxes: np.ndarray, scores: np.ndarray, iou_threshold: float = NMS_IOU) -> list[int]:
    if len(boxes) == 0:
        return []
    order = scores.argsort()[::-1]
    keep: list[int] = []
    while order.size:
        i = int(order[0])
        keep.append(i)
        if order.size == 1:
            break
        rest = boxes[order[1:]]
        xx1 = np.maximum(boxes[i, 0], rest[:, 0])
        yy1 = np.maximum(boxes[i, 1], rest[:, 1])
        xx2 = np.minimum(boxes[i, 2], rest[:, 2])
        yy2 = np.minimum(boxes[i, 3], rest[:, 3])
        inter = np.clip(xx2 - xx1, 0, None) * np.clip(yy2 - yy1, 0, None)
        area_i = max(0.0, (boxes[i, 2] - boxes[i, 0]) * (boxes[i, 3] - boxes[i, 1]))
        area_r = np.clip(rest[:, 2] - rest[:, 0], 0, None) * np.clip(rest[:, 3] - rest[:, 1], 0, None)
        iou = inter / np.maximum(area_i + area_r - inter, 1e-9)
        order = order[1:][iou <= iou_threshold]
    return keep


def detections_from_output(
    raw: np.ndarray,
    image: Image.Image,
    conf: float,
    scale: float,
    pad_x: float,
    pad_y: float,
) -> list[Detection]:
    pred = parse_yolo_output(raw)
    scores = pred[:, 4:]
    class_ids = scores.argmax(axis=1)
    confs = scores.max(axis=1)
    mask = (class_ids == PERSON_CLASS_ID) & (confs >= conf)
    if not np.any(mask):
        return []
    xyxy = scale_boxes_to_image(
        xywh_to_xyxy(pred[mask, :4]),
        scale,
        pad_x,
        pad_y,
        image.width,
        image.height,
    )
    confs = confs[mask]
    keep = nms(xyxy, confs)
    out: list[Detection] = []
    for index in keep:
        x1, y1, x2, y2 = xyxy[index]
        if x2 <= x1 or y2 <= y1:
            continue
        out.append(
            Detection(
                bbox_xyxy=[int(round(x1)), int(round(y1)), int(round(x2)), int(round(y2))],
                confidence=float(confs[index]),
                class_name="person",
            )
        )
    return out
