# SkyEye

AI-assisted missing person search & rescue tool for **RescueHacks** (Emergency Response / Community Rescue track).

SkyEye compresses the SAR triage pipeline: extract a free-text report, draw a Lost Person Behavior search ring, and scan drone-altitude photographs for human-shaped candidates. Ranked, scored boxes go to a human responder to verify.

> **SkyEye does not replace SAR teams, dispatchers, or law enforcement.** It is a triage accelerant that narrows "where do we look first" from hours to minutes. Every output is a *lead to verify*, not a confirmed location.

## What is shipped

This is the RescueHacks demo — a landing page, an operator console, and a live API.

**free-text report → Gemini/Groq extract → last-known location → geocode → Lost Person Behavior radius → Google Map pins**

**drone photograph in → tiled YOLOv8n (ONNX) → ranked person-shaped candidates → human review**

| Surface | What you get |
|---------|----------------|
| `/` | Landing. Decorative globe only — not a search map. |
| `/app` | Operator console: report intake, search ring, fixture picker, JPEG/PNG upload, boxes + pins. |
| API | Flask on port **5001** locally; Render Docker in production. Detect is ONNX Runtime. No PyTorch in the running image. |

Not in this build (and not claimed): video / live drone ingest, globe-as-product, satellite or map-tile detection, HERIDAL/SARD fine-tune. Map tiles are never detector input. Post-hackathon path: [docs/skyeye-next-steps.pdf](./docs/skyeye-next-steps.pdf). Original spec: [docs/PRD_TRD.md](./docs/PRD_TRD.md).

## The honest constraint, up front

**Satellite and map tiles cannot resolve a person.** Commercial satellite imagery tops out around 30–50 cm/pixel, which makes a human 1–2 pixels — there is nothing for a detector to find. This is a well-known limit in remote sensing, not a bug here.

So SkyEye decouples *where to look* from *what to look at*: detection runs exclusively on **drone-altitude photographs**, the altitude real SAR drones and the aerial research datasets operate at. Map tiles are a geocoding and display layer only. Three wilderness/lawn fixtures are **demo-placed** on the Bruce Trail / Milton conservation area so pins can be reviewed on the map — those photographs were not captured there, and the UI says so.

### Measured limits of the current model

Quote these numbers rather than implying the detector is better than it is:

- **Pretrained YOLOv8n has a hard floor around 60 pixels.** Subjects ≥100 px tall are detected reliably. Subjects ≤60 px are missed *entirely* — not scored below threshold, genuinely undetected. Dropping the confidence floor to 0.05 recovered none of them and added nine false positives. HERIDAL-class drone imagery puts a person at roughly 30–60 px, so this matters.
- **`TILE_SIZE` is a recall lever.** Tiles are upscaled to the network's native input, so `TILE_SIZE=320` lifts recall from 4/10 to 7/10 on a controlled scale test — at ~2.5x latency and ~5x the false positives.
- **One fixture is a permanent known miss.** `lone_surfer_shorebreak` is never detected at any threshold. It is a *pose* failure, not scale: a person lying prone on a board seen from directly above does not match COCO's upright-person prior. Tiling cannot fix it; aerial fine-tuning could. It is kept in the corpus on purpose.
- **7 of 8 demo fixtures behave as expected**, and both true-negative fixtures return zero false positives over conifer canopy and closed broadleaf canopy. Slowest fixture runs in roughly 5–8 s on a laptop CPU depending on load, against the PRD's 30 s time-to-first-lead target.

## Stack

| Layer | Tool |
|-------|------|
| Backend | Flask (`/api/health`, `/api/samples`, `/api/detect`, `/api/geocode`, `/api/extract`) |
| Detection | YOLOv8n via **ONNX Runtime** (never `torch` at request time), sliding-window tiling + IoU/containment merge |
| Intake | Gemini Flash (primary: 3.6 / 3.5-lite / 3.5 / 3.1-lite, then `gemini-flash-latest`), Groq GPT-OSS 20B then 120B (fallback) |
| Geocoding | Google Maps Geocoding API (server-side) |
| Map | Google Maps JavaScript API via `@vis.gl/react-google-maps` |
| Search radius | Simplified Lost Person Behavior 50th-percentile table |
| Frontend | Vite + React + TypeScript. Landing + console at `/app`. Decorative Three.js globe on `/` only. |
| Demo corpus | 8 openly licensed Wikimedia Commons drone photographs |
| Deploy | Vercel (UI) + Render Docker (API). Browser → Render directly. |

Maps keys are required for the search-area map. Gemini or Groq is required for free-text extract. Detection still runs without either.

## Setup

Requires **Python 3.11** (matches the Docker image) and **Node 20+**. The API runtime is ONNX Runtime, not PyTorch.

### 1. Backend

```bash
cd backend
python3.11 -m venv venv
venv/bin/python -m pip install --upgrade pip
venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
# Put GOOGLE_MAPS_API_KEY in backend/.env (Geocoding API, server-side). Never commit it.
# Put GEMINI_API_KEY and/or GROQ_API_KEY in backend/.env (LLM extract, server-side).
# Gemini is a Google AI Studio key — not the Maps key. https://aistudio.google.com/apikey
# Groq fallback: https://console.groq.com/keys
venv/bin/python fixtures/fetch_fixtures.py   # download the demo corpus (~32 MB)
venv/bin/python app.py
```

Backend serves on **http://127.0.0.1:5001**. Port 5000 is avoided because macOS AirPlay Receiver squats on it. Detect loads **ONNX Runtime** (`yolov8n.onnx`). If that file is missing, the first detect tries a one-time Ultralytics export from `yolov8n.pt` — that extra is **not** in `requirements.txt`. Either copy an onnx next to the backend, or once:

```bash
venv/bin/python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
venv/bin/python -m pip install ultralytics onnx
venv/bin/python -c "from ultralytics import YOLO; YOLO('yolov8n.pt').export(format='onnx', imgsz=640, simplify=True)"
```

Production never exports at runtime. The Docker image bakes `yolov8n.onnx` in a throwaway stage, then runs without PyTorch.

### 2. Frontend

In a second terminal:

```bash
cd frontend
cp .env.example .env.local
# Put VITE_GOOGLE_MAPS_API_KEY in frontend/.env.local (Maps JS, browser).
# Restrict that key to HTTP referrers: http://localhost:5173/*
npm install
npm run dev
```

UI on **http://localhost:5173**, proxying `/api` to Flask.

Enable **Geocoding API** and **Maps JavaScript API** on the same Google Cloud project. Prefer two restrictions: IP (or none, locally) on the server key, HTTP referrers on the browser key. A single unrestricted key works for a laptop demo and is a leak risk if the frontend is ever public.

LLM extract uses **Google AI Studio** (`GEMINI_API_KEY`) and optionally **Groq** (`GROQ_API_KEY`). Those are not Maps Platform keys. The Gemini key never goes in the frontend.

The backend rate-limits `/api/extract`, `/api/geocode`, and `/api/detect` per client IP, and separately caps outbound Gemini / Groq / Geocoding calls so a scripted loop cannot exhaust a free-tier key. Defaults stay under typical Gemini free-tier RPM. A Gemini 429 trips a short cooldown and the next extract uses Groq. Tune via `GEMINI_MAX_RPM` / `GEMINI_MAX_RPD` in `backend/.env`.

## Verify the install

```bash
backend/venv/bin/python scripts/smoke.py    # contract + behaviour checks, including geocode
backend/venv/bin/python scripts/bench.py    # per-fixture detection numbers
```

`smoke.py` covers health, sample listing and image serving, every error code, detection on an obvious-person fixture and a true negative, the upload path, a decompression-bomb guard, geocode/LPB, and extract validation (live extract when an LLM key is set). It exits non-zero on any failure. Both scripts accept `--base-url` and `--conf`.

## Run one fixture from the CLI

No server needed:

```bash
cd backend
venv/bin/python -m detection.infer fixtures/images/lone_person_on_grass.jpg
venv/bin/python -m detection.infer path/to/your.jpg --conf 0.15
venv/bin/python -m detection.infer path/to/your.jpg --no-tiling
```

Prints the same JSON shape the API returns.

## 30-second demo script

1. **Open `/` then the console.** Landing is the pitch. **Open console** goes to `/app`. Point at the amber banner: every result is a lead to verify, never a confirmation. It cannot be dismissed.
2. **Say the honest thing first** (10s): "Satellite imagery can't resolve a person — they're one or two pixels. So we detect on drone-altitude imagery, which is where SAR drones actually fly. The map is only for last-known location and a search ring."
3. **Extract the prefilled report.** The caller text is already in the box (Bruce Trail, Milton, dad, 70, red jacket). Hit Extract. Show the structured fields: last-known place, ~4.5 hours, elderly hiker. Say they are a starting point to review, not verified facts. The search form fills and the map geocodes automatically.
4. **Read the ring.** A last-known pin and an ~1.3 km Lost Person Behavior ring appear. Note it is a simplified 50th-percentile heuristic, not operational planning.
5. **Pick `Single person lying on a lawn`.** Hit Detect. One candidate returns at ~91% confidence in about 4 seconds, box tight on the person. A numbered pin appears inside the ring. Read the demo-placement notice out loud: the photo is tagged here so it can be reviewed on the map — it was not captured in Milton.
6. **Pick `Conifer stand and bare clearing`** — a true negative. Zero candidates. Read the empty state out loud: *"That is a statement about the detector, not about the ground. It does not mean nobody is there."* This is the credibility moment.
7. **If asked "how well does it work?"** — give the real numbers from the limits section above, including the 60-pixel floor and the surfer that is never detected. Then say what fixes it: fine-tuning on HERIDAL/SARD, and thermal imagery for night search, since most SAR misses happen after dark.

Optional, if there is time: `Busy beachfront` shows tiling and cross-tile merge doing real work on many small subjects. If extract has no key, skip step 3 and geocode the prefilled search-area form by hand.

## Architecture

```
frontend/                     Vite + React
  src/Root.tsx                `/` landing · `/app` console
  src/landing/                LandingPage, decorative GlobeScene (Three.js)
  src/components/             SafetyBanner, ReportIntake, SearchArea, SearchMap,
                              DetectPanel, SamplePicker, UploadZone,
                              DetectionOverlay, DetectionList
  src/api/client.ts           typed fetch wrappers, 180s abort
backend/
  app.py                      Flask app factory
  config.py                   env-backed settings (version 0.3.0)
  ratelimit.py                in-process sliding-window + Gemini/Groq/Maps budgets
  gunicorn.conf.py            1 gthread worker, 180s timeout (Render)
  Dockerfile                  export stage → yolov8n.onnx; slim runtime, no torch
  api/                        health, samples, detect, geocode, extract, error shape
  extract/                    Gemini primary, Groq GPT-OSS fallback, field normalize
  geo/                        LPB radius, Google geocoder, pixel→lat/lng
  detection/
    model.py                  lazy ONNX session, person-class filter (no torch import)
    onnx_infer.py             letterbox + NMS
    tiling.py                 sliding window + box projection
    merge.py                  IoU + containment NMS across tile seams
    infer.py                  detect_full_image, detect_image, CLI
  fixtures/                   manifest.json + fetch script (blobs gitignored)
scripts/                      smoke.py, bench.py
docs/
  api-contract.md             frozen request/response shapes
  PRD_TRD.md                  product + technical requirements (shipped vs stretch)
  deploy.md                   Vercel UI + Render API
  skyeye-next-steps.pdf       post-hackathon briefing
```

The API contract in [docs/api-contract.md](./docs/api-contract.md) is frozen: change it there before changing code on either side. Pipeline diagram: [docs/demo-architecture-flowchart.png](./docs/demo-architecture-flowchart.png).

## Deploy

Production is **Vercel** (Vite UI) + **Render** (Flask + YOLOv8n ONNX). The browser calls Render directly — do not proxy `/api` through Vercel, or detect will time out. The API image does not ship PyTorch; detect loads ONNX Runtime instead.

Step-by-step, env vars, and the live smoke list: [docs/deploy.md](./docs/deploy.md). Blueprint: [render.yaml](./render.yaml).

## Safety and responsible design

- Non-dismissible banner on the console; the same sentence is in the landing footer: *"SkyEye surfaces possible leads only. It does not confirm a person's location or safety. Contact 911 / local SAR immediately."*
- Confidence is always shown explicitly. The words "found", "located", and "confirmed" appear nowhere in the UI.
- Zero results are never reported as "the area is clear".
- No feature suggests the user personally investigate a detection.
- All demo imagery is pre-existing, openly licensed public data. No live surveillance, no scraped footage. Per-fixture source, license, and attribution live in `backend/fixtures/manifest.json` and are surfaced in the UI.

## Demo corpus

Eight openly licensed nadir/near-nadir drone photographs from Wikimedia Commons: two obvious-person, four cluttered, two true-negative. Image blobs are gitignored; `backend/fixtures/fetch_fixtures.py` re-downloads them.

The purpose-built aerial SAR datasets (**HERIDAL**, **SARD**, **C2A**) are gated behind request forms or Kaggle authentication and are not used here. The substitute corpus has the same core difficulty — humans occupying a few dozen pixels in cluttered overhead imagery — and the substitution is recorded in the manifest rather than glossed over.

## Source

Original spec: [SkyEye_PRD_TRD on Notion](https://app.notion.com/p/3c88fa97c148804c9477c3feca09cefb)
