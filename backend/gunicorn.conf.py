"""Gunicorn settings for Render (and any other 0.0.0.0 deploy).

One worker: YOLOv8n + tiling is memory-heavy; a second worker will OOM on
the 2 GB plan. gthread keeps /api/health responsive during a long detect.
"""

import os

bind = f"0.0.0.0:{os.environ.get('PORT', '10000')}"
worker_class = "gthread"
workers = 1
threads = 4
timeout = 180
graceful_timeout = 30
keepalive = 5
accesslog = "-"
errorlog = "-"
loglevel = "info"
