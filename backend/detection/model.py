"""Lazy YOLO loading so process start never blocks on weights."""

from __future__ import annotations

import threading

from config import settings

_model = None
_lock = threading.Lock()

PERSON_CLASS_NAME = "person"


def is_loaded() -> bool:
    return _model is not None


def get_model():
    """Load the configured weights once and reuse the instance."""
    global _model
    if _model is not None:
        return _model
    with _lock:
        if _model is None:
            from ultralytics import YOLO

            model = YOLO(settings.weights)
            model.to(settings.device)
            _model = model
    return _model


def person_class_ids(model) -> list[int]:
    names = getattr(model, "names", {}) or {}
    return [int(idx) for idx, name in names.items() if str(name).lower() == PERSON_CLASS_NAME]
