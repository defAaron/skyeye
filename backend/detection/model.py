"""Lazy YOLO loading so process start never blocks on weights."""

from __future__ import annotations

import logging
import os
import threading

from config import settings

logger = logging.getLogger(__name__)

_model = None
_lock = threading.Lock()

PERSON_CLASS_NAME = "person"


def is_loaded() -> bool:
    return _model is not None


def _configure_torch_threads() -> None:
    """Cap BLAS/PyTorch threads before the first import.

    Default 1 keeps RSS down on Render. A second worker or a wide thread pool
    is what turns a 2 GB box into status 137 on first detect.
    """
    threads = max(1, int(settings.torch_num_threads))
    os.environ.setdefault("OMP_NUM_THREADS", str(threads))
    os.environ.setdefault("MKL_NUM_THREADS", str(threads))
    os.environ.setdefault("OPENBLAS_NUM_THREADS", str(threads))
    import torch

    torch.set_num_threads(threads)
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        # Already set for this process; a second detect must not crash.
        pass


def get_model():
    """Load the configured weights once and reuse the instance."""
    global _model
    if _model is not None:
        return _model
    with _lock:
        if _model is None:
            _configure_torch_threads()
            from ultralytics import YOLO

            model = YOLO(settings.weights)
            model.to(settings.device)
            _model = model
            logger.info(
                "yolo loaded weights=%s device=%s threads=%s",
                settings.weights_label,
                settings.device,
                settings.torch_num_threads,
            )
    return _model


def person_class_ids(model) -> list[int]:
    names = getattr(model, "names", {}) or {}
    return [int(idx) for idx, name in names.items() if str(name).lower() == PERSON_CLASS_NAME]
