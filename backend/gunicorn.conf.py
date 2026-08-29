"""Gunicorn settings for Render (and any other 0.0.0.0 deploy).

One worker: YOLOv8n + tiling is memory-heavy; a second worker will OOM on
the 2 GB plan. Two gthread workers' worth of concurrent detect also doubles
RSS — keep threads at 2 so /api/health still answers during a long run.
"""

import os

bind = f"0.0.0.0:{os.environ.get('PORT', '10000')}"
worker_class = "gthread"
workers = 1
threads = 2
timeout = 180
graceful_timeout = 30
keepalive = 5
accesslog = "-"
errorlog = "-"
loglevel = "info"
