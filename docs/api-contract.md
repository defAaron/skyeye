# SkyEye API contract (core detection phase)

Frozen for the core build: **image in → ranked person-shaped candidates out → human review**.

This document is the single source of truth for request/response shapes in this phase. No agent may change a shape here without editing this file in the same change. Map, LLM extraction, geocoding, and globe features are **not** part of this contract; see [PRD_TRD.md](PRD_TRD.md) for the later product vision.

**Imagery rule:** detection runs on drone-altitude photos. Satellite/map tiles cannot resolve a person (~30–50 cm/pixel makes a human 1–2 pixels), so they are never detector input.

---

## Repository layout

```
skyeye/
├── backend/
│   ├── app.py                  # Flask app factory + entrypoint
│   ├── config.py               # env-backed settings (limits, weights, CORS)
│   ├── requirements.txt
│   ├── api/
│   │   ├── __init__.py
│   │   ├── health.py           # GET /api/health
│   │   ├── samples.py          # GET /api/samples, GET /api/samples/<id>/image
│   │   └── detect.py           # POST /api/detect
│   ├── detection/
│   │   ├── __init__.py
│   │   ├── model.py            # lazy YOLO load, person-class filter
│   │   ├── tiling.py           # sliding window + box projection
│   │   ├── merge.py            # IoU/NMS merge across tiles
│   │   └── infer.py            # detect_full_image() + CLI
│   └── fixtures/
│       ├── manifest.json       # curated demo corpus metadata
│       └── images/             # local demo images (gitignored blobs)
├── frontend/
│   ├── package.json
│   ├── vite.config.ts          # /api proxy → Flask
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── api/client.ts       # typed fetch wrappers
│       ├── types.ts            # mirrors this contract
│       └── components/         # SafetyBanner, SamplePicker, DetectionOverlay, ...
└── docs/
    ├── api-contract.md
    └── PRD_TRD.md
```

Ownership (one agent per area per step): `backend/detection/` = ML, `backend/app.py` + `backend/api/` = Backend, `frontend/src/` = Frontend, `backend/fixtures/` = Data.

---

## Conventions

- Base URL in dev: `http://127.0.0.1:5001`. The frontend calls relative `/api/*` and Vite proxies to it.
- All responses are JSON, `Content-Type: application/json`, except sample image bytes.
- Coordinates are **pixel space** on the submitted image, origin top-left, `[x_min, y_min, x_max, y_max]` as integers.
- `lat` / `lng` exist on every detection and are **always `null`** in this phase. They are reserved for the later geocoding layer and must not be removed.
- Detections are sorted by `confidence` descending. `id` is stable within one response (`d1`, `d2`, …).
- Every detection response carries `disclaimer`. Clients must display it and must never render "found".

### Errors

All errors use one shape and never leak filesystem paths, stack traces, or config:

```json
{ "error": { "code": "IMAGE_TOO_LARGE", "message": "Image exceeds the 40 megapixel limit." } }
```

| HTTP | `code` | When |
|------|--------|------|
| 400 | `NO_IMAGE` | Neither `image` nor `sample_id` supplied |
| 400 | `AMBIGUOUS_INPUT` | Both `image` and `sample_id` supplied |
| 400 | `UNSUPPORTED_TYPE` | Not JPEG or PNG |
| 400 | `INVALID_IMAGE` | Bytes are not a decodable image |
| 404 | `SAMPLE_NOT_FOUND` | Unknown `sample_id` |
| 413 | `FILE_TOO_LARGE` | Upload exceeds `MAX_UPLOAD_BYTES` |
| 413 | `IMAGE_TOO_LARGE` | Decoded pixels exceed `MAX_IMAGE_PIXELS` |
| 500 | `INFERENCE_FAILED` | Model load or inference error |
| 503 | `MODEL_UNAVAILABLE` | Weights missing / not yet downloaded |

---

## `GET /api/health`

Liveness plus enough capability info for the UI to warn early.

```json
{
  "status": "ok",
  "version": "0.1.0",
  "model": { "loaded": false, "weights": "yolov8n.pt", "device": "cpu" },
  "limits": {
    "max_upload_bytes": 26214400,
    "max_image_pixels": 40000000,
    "allowed_types": ["image/jpeg", "image/png"]
  }
}
```

`model.loaded` is `false` until the first detect request warms the model (lazy load). `status` is `"ok"` whenever the process serves requests; it never depends on model warmth.

---

## `GET /api/samples`

Lists the curated demo corpus from `backend/fixtures/manifest.json`. No filesystem paths are exposed.

```json
{
  "samples": [
    {
      "id": "obvious_person_field",
      "label": "Single hiker in open field",
      "scenario": "obvious_person",
      "width": 4000,
      "height": 3000,
      "terrain": "open grass and scattered scrub",
      "source": "Wikimedia Commons — \"Example Aerial (Unsplash)\"",
      "source_url": "https://commons.wikimedia.org/wiki/File:Example.jpg",
      "license": "CC0",
      "attribution": "Photographer name via Unsplash",
      "expected_min_detections": 1,
      "image_url": "/api/samples/obvious_person_field/image"
    }
  ]
}
```

`scenario` is one of `obvious_person`, `cluttered`, `true_negative`. `expected_min_detections` is `0` for `true_negative` and drives the smoke test.

`license`, `attribution`, and `source_url` are served because several fixtures are CC BY / CC BY-SA and the UI must be able to credit them. Only fixtures whose image file is present on disk are listed, so a clone that has not run the download script returns `{"samples": []}` rather than broken entries.

### Client-only error codes

The client may raise these in the same `{ error: { code, message } }` shape. They never come from the server, so they are not in the HTTP table above:

| `code` | When |
|--------|------|
| `NETWORK_ERROR` | Request never reached the backend |
| `BAD_RESPONSE` | Response was not the expected JSON |
| `TIMEOUT` | Client aborted after its own deadline (~180s) |
| `CANCELLED` | User abandoned the request |

## `GET /api/samples/<id>/image`

Returns the fixture bytes (`image/jpeg` or `image/png`) so the UI can display and overlay boxes without re-uploading. `404` with `SAMPLE_NOT_FOUND` for unknown ids. Ids are matched against the manifest only — never joined into a path from raw user input.

---

## `POST /api/detect`

`multipart/form-data`. Exactly one image source.

| Field | Type | Notes |
|-------|------|-------|
| `image` | file | JPEG or PNG upload |
| `sample_id` | string | Fixture id from `/api/samples`, instead of `image` |
| `conf` | float | Optional confidence floor, `0.01`–`0.95`, default from env |

### Response `200`

```json
{
  "image_width": 4000,
  "image_height": 3000,
  "detections": [
    {
      "id": "d1",
      "bbox_xyxy": [120, 40, 180, 160],
      "confidence": 0.78,
      "class_name": "person",
      "lat": null,
      "lng": null
    }
  ],
  "meta": {
    "source": "sample",
    "sample_id": "obvious_person_field",
    "tiles": 42,
    "conf_threshold": 0.25,
    "inference_ms": 3120,
    "model": "yolov8n.pt"
  },
  "disclaimer": "SkyEye surfaces possible leads only. It does not confirm a person's location or safety. Contact 911 / local SAR immediately."
}
```

`detections` is `[]` for a true negative — that is a success, not an error. `meta.source` is `"upload"` or `"sample"`; `sample_id` is `null` for uploads.

---

## Environment variables (`backend/.env`, template in `backend/.env.example`)

| Var | Default | Purpose |
|-----|---------|---------|
| `FLASK_PORT` | `5001` | Dev server port (5000 collides with macOS AirPlay) |
| `CORS_ORIGIN` | `http://localhost:5173` | Single allowed origin for the Vite dev server |
| `YOLO_WEIGHTS` | `yolov8n.pt` | Weights path; swapped by Step 1.5 if fine-tuning happens |
| `YOLO_DEVICE` | `cpu` | `cpu`, `mps`, or `cuda` |
| `CONF_THRESHOLD` | `0.25` | Default confidence floor |
| `TILE_SIZE` | `640` | Sliding-window tile edge in pixels |
| `TILE_OVERLAP` | `0.2` | Fractional tile overlap |
| `MAX_UPLOAD_BYTES` | `26214400` | 25 MB request cap |
| `MAX_IMAGE_PIXELS` | `40000000` | 40 MP decoded-pixel cap |

No secrets are needed in this phase. API keys (Gemini, Google Maps) belong to later phases and must never be committed.
