"""Lazy ONNX YOLO load. Never import torch at runtime — that is the 137 OOM."""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path

from PIL import Image

from config import settings
from detection.onnx_infer import detections_from_output, image_to_nchw, letterbox
from detection.types import Detection

logger = logging.getLogger(__name__)

_model = None
_lock = threading.Lock()

PERSON_CLASS_NAME = "person"
INPUT_SIZE = 640


class ModelUnavailableError(Exception):
    """Weights are not on disk and cannot be exported in this environment."""


class OnnxYolo:
    """Thin ONNX Runtime session. One image at a time to keep RSS down."""

    names = {0: PERSON_CLASS_NAME}

    def __init__(self, path: Path) -> None:
        import onnxruntime as ort

        options = ort.SessionOptions()
        threads = max(1, int(settings.torch_num_threads))
        options.intra_op_num_threads = threads
        options.inter_op_num_threads = 1
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.session = ort.InferenceSession(
            str(path),
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )
        self.input_name = self.session.get_inputs()[0].name
        self.path = path

    def infer(self, image: Image.Image, conf: float) -> list[Detection]:
        boxed, scale, pad_x, pad_y = letterbox(image, INPUT_SIZE)
        output = self.session.run(None, {self.input_name: image_to_nchw(boxed)})[0]
        return detections_from_output(output, image, conf, scale, pad_x, pad_y)


def is_loaded() -> bool:
    return _model is not None


def resolve_onnx_weights() -> Path:
    """Prefer a sibling .onnx so Render can keep YOLO_WEIGHTS=*.pt in the dashboard."""
    raw = Path(settings.weights)
    if raw.suffix.lower() == ".onnx":
        return raw
    sibling = raw.with_suffix(".onnx")
    if sibling.is_file():
        return sibling
    return raw if raw.suffix.lower() == ".onnx" else sibling


def _export_onnx_from_pt(pt_path: Path, onnx_path: Path) -> None:
    """One-time local export. Render images already bake the .onnx file."""
    from ultralytics import YOLO

    exported = Path(YOLO(str(pt_path)).export(format="onnx", imgsz=INPUT_SIZE, simplify=True))
    if exported.resolve() != onnx_path.resolve():
        onnx_path.parent.mkdir(parents=True, exist_ok=True)
        exported.replace(onnx_path)


def get_model() -> OnnxYolo:
    """Load the ONNX session once and reuse it."""
    global _model
    if _model is not None:
        return _model
    with _lock:
        if _model is None:
            os.environ.setdefault("OMP_NUM_THREADS", str(max(1, int(settings.torch_num_threads))))
            onnx_path = resolve_onnx_weights()
            if not onnx_path.is_file():
                pt_path = Path(settings.weights)
                if pt_path.suffix.lower() != ".pt":
                    pt_path = pt_path.with_suffix(".pt")
                if not pt_path.is_file():
                    raise ModelUnavailableError("ONNX weights are not available.")
                logger.info("exporting onnx from %s", pt_path.name)
                _export_onnx_from_pt(pt_path, onnx_path)
            if not onnx_path.is_file():
                raise ModelUnavailableError("ONNX weights are not available.")
            _model = OnnxYolo(onnx_path)
            logger.info("yolo onnx loaded weights=%s", onnx_path.name)
    return _model


def person_class_ids(model) -> list[int]:
    names = getattr(model, "names", {}) or {}
    return [int(idx) for idx, name in names.items() if str(name).lower() == PERSON_CLASS_NAME]
