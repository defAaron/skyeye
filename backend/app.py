from __future__ import annotations

import logging

from flask import Flask
from flask_cors import CORS
from PIL import Image

from api.detect import bp as detect_bp
from api.errors import register_error_handlers
from api.extract import bp as extract_bp
from api.geocode import bp as geocode_bp
from api.health import bp as health_bp
from api.samples import bp as samples_bp
from config import settings


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = settings.max_upload_bytes

    # Pillow's own bomb ceiling defaults to ~89 MP, well above our cap, which would let
    # 40-89 MP images decode in full before the handler rejects them.
    Image.MAX_IMAGE_PIXELS = settings.max_image_pixels

    CORS(app, resources={r"/api/*": {"origins": [settings.cors_origin]}})

    app.register_blueprint(health_bp)
    app.register_blueprint(samples_bp)
    app.register_blueprint(detect_bp)
    app.register_blueprint(geocode_bp)
    app.register_blueprint(extract_bp)
    register_error_handlers(app)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=settings.port, debug=False)
