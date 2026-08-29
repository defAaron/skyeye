# CPU-only inference image for Render. Python 3.11 — PyTorch has no 3.13+ wheels
# we can rely on, and the laptop venv is already 3.11.
#
# Build context is the REPO ROOT (Render default), not backend/:
#   docker build -f backend/Dockerfile .
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    YOLO_DEVICE=cpu \
    YOLO_WEIGHTS=/app/yolov8n.pt \
    YOLO_CONFIG_DIR=/tmp/Ultralytics \
    MPLCONFIGDIR=/tmp/matplotlib \
    OMP_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    NUMEXPR_NUM_THREADS=1 \
    MALLOC_ARENA_MAX=2

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt .
# CPU torch first so ultralytics does not pull a CUDA wheel.
RUN pip install --upgrade pip \
    && pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu \
    && pip install -r requirements.txt

# Weights at build time so the first /api/detect is not a 503 + multi-minute download.
RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"

COPY backend/fixtures/manifest.json fixtures/manifest.json
COPY backend/fixtures/fetch_fixtures.py fixtures/fetch_fixtures.py
RUN mkdir -p fixtures/images && python fixtures/fetch_fixtures.py

COPY backend/ .

EXPOSE 10000

CMD ["gunicorn", "--config", "gunicorn.conf.py", "app:app"]
