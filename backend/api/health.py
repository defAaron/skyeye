from __future__ import annotations

from flask import Blueprint, jsonify

from config import VERSION, settings

bp = Blueprint("health", __name__)


@bp.get("/api/health")
def health():
    from detection import model as model_module

    return jsonify(
        {
            "status": "ok",
            "version": VERSION,
            "model": {
                "loaded": model_module.is_loaded(),
                "weights": settings.weights_label,
                "device": settings.device,
            },
            "geocode": {"configured": settings.geocode_configured},
            "extract": {
                "configured": settings.extract_configured,
                "gemini": settings.gemini_configured,
                "groq": settings.groq_configured,
            },
            "limits": settings.limits_payload(),
        }
    )
