# Runtime image has no PyTorch. Export YOLOv8n to ONNX in a throwaway stage so
# /api/detect cannot OOM a 512 MB–2 GB Render box by importing torch.
#
# Build context is the REPO ROOT (Render default), not backend/:
#   docker build -f backend/Dockerfile .
FROM python:3.11-slim-bookworm AS export

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    YOLO_CONFIG_DIR=/tmp/Ultralytics \
    MPLCONFIGDIR=/tmp/matplotlib

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

RUN pip install --upgrade pip \
    && pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu \
    && pip install ultralytics onnx \
    && python -c "from ultralytics import YOLO; YOLO('yolov8n.pt').export(format='onnx', imgsz=640, simplify=True)"

FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    YOLO_DEVICE=cpu \
    YOLO_WEIGHTS=/app/yolov8n.onnx \
    OMP_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    NUMEXPR_NUM_THREADS=1 \
    MALLOC_ARENA_MAX=2 \
    ORT_INTRA_OP_NUM_THREADS=1 \
    ORT_INTER_OP_NUM_THREADS=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY --from=export /build/yolov8n.onnx /app/yolov8n.onnx

COPY backend/fixtures/manifest.json fixtures/manifest.json
COPY backend/fixtures/fetch_fixtures.py fixtures/fetch_fixtures.py
RUN mkdir -p fixtures/images && python fixtures/fetch_fixtures.py

COPY backend/ .

EXPOSE 10000

CMD ["gunicorn", "--config", "gunicorn.conf.py", "app:app"]
