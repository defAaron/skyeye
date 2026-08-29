# SkyEye API contract (core detection + search-area map + LLM intake)

Frozen for this build: **image in → ranked person-shaped candidates out → human review**, plus **report text → LLM extract → geocode + LPB radius → map pins**.

This document is the single source of truth for request/response shapes. No agent may change a shape here without editing this file in the same change. Globe view and video upload are **not** part of this contract; see [PRD_TRD.md](PRD_TRD.md).

**Imagery rule:** detection runs on drone-altitude photos. Satellite/map tiles cannot resolve a person (~30–50 cm/pixel makes a human 1–2 pixels), so they are never detector input. Google Maps is a geocoding and display layer only.

---

## Repository layout

```
skyeye/
├── backend/
│   ├── app.py                  # Flask app factory + entrypoint
│   ├── config.py               # env-backed settings (limits, weights, CORS)
│   ├── ratelimit.py            # in-process sliding-window + Gemini/Groq/Maps budgets
│   ├── gunicorn.conf.py        # 1 gthread worker, 180s timeout (Render)
│   ├── Dockerfile              # CPU torch + fixtures + weights
│   ├── requirements.txt
│   ├── api/
│   │   ├── __init__.py
│   │   ├── health.py           # GET /api/health
│   │   ├── samples.py          # GET /api/samples, GET /api/samples/<id>/image
│   │   ├── detect.py           # POST /api/detect
│   │   ├── geocode.py          # POST /api/geocode
│   │   └── extract.py          # POST /api/extract
│   ├── extract/
│   │   ├── normalize.py        # clip hours, map category, drop empty location
│   │   └── providers.py        # Gemini primary, Groq fallback
│   ├── geo/
│   │   ├── lpb.py              # Lost Person Behavior radius table
│   │   ├── geocoder.py         # Google Geocoding API client
│   │   └── project.py          # pixel → lat/lng for georeferenced samples
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
│   ├── vite.config.ts          # /api proxy → Flask (dev)
│   ├── vercel.json             # /app → index.html
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

- Base URL in dev: `http://127.0.0.1:5001`. The frontend calls `/api/*` (relative in Vite, prefixed by `VITE_API_BASE_URL` on Vercel) and Vite proxies to Flask locally. Production API is the Render origin; do not proxy detect through Vercel.
- All responses are JSON, `Content-Type: application/json`, except sample image bytes.
- Coordinates on the image are **pixel space**, origin top-left, `[x_min, y_min, x_max, y_max]` as integers.
- `lat` / `lng` exist on every detection. They are WGS84 numbers when the submitted sample is georeferenced; otherwise both are `null`. They are always `null` for uploads. Both are numbers or both are `null` — never mixed.
- Detections stay sorted by `confidence` descending. `id` is stable within one response (`d1`, `d2`, …).
- Every detection response carries `disclaimer`. Clients must display it and must never render "found".
- Google Maps, Gemini, and Groq API keys must never appear in responses, logs, or the git tree. Report text is PII-adjacent: log length only, never the body.

### Errors

All errors use one shape and never leak filesystem paths, stack traces, or config. `429 RATE_LIMITED` also sets `Retry-After` (seconds).

```json
{ "error": { "code": "IMAGE_TOO_LARGE", "message": "Image exceeds the 40 megapixel limit." } }
```

| HTTP | `code` | When |
|------|--------|------|
| 400 | `NO_IMAGE` | Neither `image` nor `sample_id` supplied |
| 400 | `AMBIGUOUS_INPUT` | Both `image` and `sample_id` supplied |
| 400 | `UNSUPPORTED_TYPE` | Not JPEG or PNG |
| 400 | `INVALID_IMAGE` | Bytes are not a decodable image |
| 400 | `INVALID_CONF` | `conf` missing-as-invalid or outside `0.01`–`0.95` |
| 400 | `EMPTY_LOCATION` | Geocode `location_text` missing or blank |
| 400 | `LOCATION_TOO_LONG` | Geocode `location_text` exceeds 200 characters |
| 400 | `INVALID_ELAPSED_HOURS` | `elapsed_hours` missing or outside `0.1`–`72` |
| 400 | `UNKNOWN_CATEGORY` | `category` is not in the LPB table |
| 400 | `EMPTY_REPORT` | Extract `report_text` missing or blank |
| 400 | `REPORT_TOO_LONG` | Extract `report_text` exceeds 4000 characters |
| 400 | `EXTRACT_INCOMPLETE` | Model returned JSON with no usable `location_text` |
| 404 | `SAMPLE_NOT_FOUND` | Unknown `sample_id` |
| 404 | `GEOCODE_NOT_FOUND` | Google returned zero results for that text |
| 413 | `FILE_TOO_LARGE` | Upload exceeds `MAX_UPLOAD_BYTES` |
| 413 | `IMAGE_TOO_LARGE` | Decoded pixels exceed `MAX_IMAGE_PIXELS` |
| 500 | `INFERENCE_FAILED` | Model load or inference error |
| 502 | `GEOCODE_FAILED` | Geocoding provider error (no key leaked) |
| 502 | `EXTRACT_FAILED` | Gemini and Groq both failed (no key leaked) |
| 503 | `MODEL_UNAVAILABLE` | Weights missing / not yet downloaded |
| 503 | `GEOCODE_UNAVAILABLE` | `GOOGLE_MAPS_API_KEY` unset, or provider denied the request |
| 503 | `EXTRACT_UNAVAILABLE` | Neither `GEMINI_API_KEY` nor `GROQ_API_KEY` set, or both providers denied the request |
| 429 | `RATE_LIMITED` | Per-IP or provider budget exceeded. `Retry-After` is set to seconds until a slot frees. |

---

## `GET /api/health`

Liveness plus enough capability info for the UI to warn early.

```json
{
  "status": "ok",
  "version": "0.3.0",
  "model": { "loaded": false, "weights": "yolov8n.pt", "device": "cpu" },
  "geocode": { "configured": false },
  "extract": { "configured": false, "gemini": false, "groq": false },
  "limits": {
    "max_upload_bytes": 26214400,
    "max_image_pixels": 40000000,
    "allowed_types": ["image/jpeg", "image/png"]
  }
}
```

`model.loaded` is `false` until the first detect request warms the model (lazy load). `status` is `"ok"` whenever the process serves requests; it never depends on model warmth. `geocode.configured` is `true` when `GOOGLE_MAPS_API_KEY` is non-empty — the key itself is never returned. `extract.gemini` / `extract.groq` are `true` when the matching key is non-empty. `extract.configured` is `true` when either provider key is set. Keys are never returned.

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
      "image_url": "/api/samples/obvious_person_field/image",
      "geo": {
        "center_lat": 43.5094,
        "center_lng": -79.9518,
        "demo_placement": true
      }
    }
  ]
}
```

`scenario` is one of `obvious_person`, `cluttered`, `true_negative`. `expected_min_detections` is `0` for `true_negative` and drives the smoke test.

`geo` is `null` when the fixture is not tagged to a map location. When present, `demo_placement` is `true` if the photograph was **not** captured at those coordinates — it is tagged there so detections can be reviewed on the map. Clients must not describe that as the photo’s real origin.

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
      "lat": 43.50951,
      "lng": -79.95172
    }
  ],
  "meta": {
    "source": "sample",
    "sample_id": "obvious_person_field",
    "tiles": 42,
    "conf_threshold": 0.25,
    "inference_ms": 3120,
    "model": "yolov8n.pt",
    "geo": {
      "center_lat": 43.5094,
      "center_lng": -79.9518,
      "gsd_m": 0.15,
      "heading_deg": 0,
      "demo_placement": true
    }
  },
  "disclaimer": "SkyEye surfaces possible leads only. It does not confirm a person's location or safety. Contact 911 / local SAR immediately."
}
```

`detections` is `[]` for a true negative — that is a success, not an error. `meta.source` is `"upload"` or `"sample"`; `sample_id` is `null` for uploads. `meta.geo` is `null` when the image is not georeferenced (uploads, and fixtures without a `geo` block). When `demo_placement` is `true`, `lat`/`lng` are a map overlay for the demo, not GPS from the aircraft.

---

## `POST /api/geocode`

`application/json`. Converts last-known-location text into a map center and a Lost Person Behavior search radius. Does **not** run detection.

```json
// Request
{
  "location_text": "Bruce Trail, Milton, Ontario",
  "elapsed_hours": 4.5,
  "category": "elderly_hiker"
}
```

```json
// Response 200
{
  "lat": 43.5085,
  "lng": -79.9521,
  "formatted_address": "Bruce Trail, Milton, ON, Canada",
  "radius_m": 1347,
  "category": "elderly_hiker",
  "elapsed_hours": 4.5,
  "lpb_note": "Simplified 50th-percentile Lost Person Behavior radius, scaled with elapsed time. Not a guarantee the subject is inside the ring."
}
```

| Field | Rules |
|-------|--------|
| `location_text` | Required string, 1–200 characters after trim |
| `elapsed_hours` | Required number, `0.1`–`72` |
| `category` | Required. One of `child`, `youth`, `elderly`, `elderly_hiker`, `dementia`, `hiker`, `hunter`, `unknown` |

Radius formula (frozen): `clip(p50_m[category] * sqrt(elapsed_hours / 3), 200, 8000)` meters. `p50_m` is a simplified Koester-style 50th-percentile table treated as the radius at 3 elapsed hours. This is a demo heuristic, not operational SAR planning.

The backend calls Google Maps Geocoding API. The key never appears in the response. First result wins.

---

## `POST /api/extract`

`application/json`. Turns a free-text missing-person report into structured fields a responder can review. Does **not** geocode or run detection.

```json
// Request
{
  "report_text": "My dad went missing around 3pm near Bruce Trail, Milton. He's 70, wearing a red jacket, last seen walking near the conservation area entrance."
}
```

```json
// Response 200
{
  "location_text": "Bruce Trail, Milton",
  "time_last_seen": "15:00",
  "elapsed_hours": 4.5,
  "subject": {
    "age": 70,
    "clothing": "red jacket",
    "distinguishing_features": null,
    "category": "elderly_hiker"
  },
  "terrain_hint": "wooded trail",
  "provider": "gemini",
  "disclaimer": "Extracted fields are a starting point for a responder to review. They are not verified facts."
}
```

| Field | Rules |
|-------|--------|
| `report_text` | Required string, 1–4000 characters after trim |

Response rules:

- `location_text` is a geocodable place (1–200 chars). Empty after the model runs → `EXTRACT_INCOMPLETE`.
- `elapsed_hours` is clipped to `0.1`–`72`. If the model omits it, default `3.0`.
- `subject.category` is one of the LPB table values. Unknown labels become `unknown`.
- `subject.age` is an integer `0`–`120`, or `null`.
- `time_last_seen`, `clothing`, `distinguishing_features`, `terrain_hint` are strings or `null`.
- `provider` is `"gemini"` or `"groq"` — which model produced the JSON. Never a key.
- `disclaimer` is always present. Clients must display it. Extracted fields are not verified facts.

Provider order: Gemini Flash first (`gemini-3.6-flash`, `gemini-3.5-flash-lite`, `gemini-3.5-flash`, `gemini-3.1-flash-lite`, then `gemini-flash-latest`); Groq `openai/gpt-oss-20b` then `openai/gpt-oss-120b` if Gemini is unset, quota-limited, locally rate-limited, or fails. Neither key appears in the response. The report body is never logged.

### Rate limits

In-process sliding windows (reset on process restart). They exist so a tight UI loop or a scripted client cannot burn `GEMINI_API_KEY`, `GROQ_API_KEY`, or `GOOGLE_MAPS_API_KEY`. Limits are not returned from `/api/health`. `X-Forwarded-For` is ignored unless `TRUST_PROXY=1`, in which case ProxyFix takes the single hop the reverse proxy added.

| Guard | Default | What it protects |
|-------|---------|------------------|
| Per-IP `/api/extract` | 8/min, 20/day | Gemini + Groq keys |
| Per-IP `/api/geocode` | 10/min, 80/day | Maps Geocoding key |
| Per-IP `/api/detect` | 20/min, 80/day | CPU / model |
| Gemini global | 8 RPM, 200 RPD | `GEMINI_API_KEY` (under typical free-tier 10–15 RPM) |
| Groq global | 20 RPM, 500 RPD | `GROQ_API_KEY` |
| Geocode global | 20 RPM, 400 RPD | `GOOGLE_MAPS_API_KEY` |

A Gemini 429 from Google trips a 60 s cooldown so the next extract skips Gemini and uses Groq. Hitting the per-IP extract cap returns `429 RATE_LIMITED` without calling either provider. Hitting the Gemini budget (or cooldown) skips Gemini only.

---

## Environment variables

### Backend (`backend/.env`, template in `backend/.env.example`)

| Var | Default | Purpose |
|-----|---------|---------|
| `FLASK_PORT` | `5001` | Dev server port (5000 collides with macOS AirPlay) |
| `CORS_ORIGIN` | `http://localhost:5173` | Allowed browser origins, comma-separated |
| `CORS_ORIGIN_REGEX` | _(empty)_ | Optional extra origin regex (e.g. Vercel previews) |
| `TRUST_PROXY` | unset / false | `1` on Render so ProxyFix rewrites `remote_addr` from the proxy hop |
| `YOLO_WEIGHTS` | `yolov8n.pt` | Weights path; swapped by Step 1.5 if fine-tuning happens |
| `YOLO_DEVICE` | `cpu` | `cpu`, `mps`, or `cuda` |
| `CONF_THRESHOLD` | `0.25` | Default confidence floor |
| `TILE_SIZE` | `640` | Sliding-window tile edge in pixels |
| `TILE_OVERLAP` | `0.2` | Fractional tile overlap |
| `TILE_BATCH_SIZE` | `1` | Tiles per YOLO forward. Keep `1` on Render; `4`–`8` on a laptop with RAM to spare |
| `TORCH_NUM_THREADS` | `1` | PyTorch/OMP threads. `1` avoids a 137 OOM on a 2 GB instance |
| `MAX_UPLOAD_BYTES` | `26214400` | 25 MB request cap |
| `MAX_IMAGE_PIXELS` | `40000000` | 40 MP decoded-pixel cap |
| `GOOGLE_MAPS_API_KEY` | _(empty)_ | Server-side Geocoding API. Never commit. |
| `GEMINI_API_KEY` | _(empty)_ | Server-side Gemini Flash. Never commit. |
| `GROQ_API_KEY` | _(empty)_ | Server-side Groq fallback. Never commit. |
| `GEMINI_MAX_RPM` | `8` | Process-wide Gemini calls per rolling minute |
| `GEMINI_MAX_RPD` | `200` | Process-wide Gemini calls per rolling day |
| `GEMINI_COOLDOWN_SECONDS` | `60` | Skip Gemini this long after a provider 429 |
| `GROQ_MAX_RPM` | `20` | Process-wide Groq calls per rolling minute |
| `GROQ_MAX_RPD` | `500` | Process-wide Groq calls per rolling day |
| `GROQ_COOLDOWN_SECONDS` | `30` | Skip Groq this long after a provider 429 |
| `GEOCODE_MAX_RPM` | `20` | Process-wide Geocoding calls per rolling minute |
| `GEOCODE_MAX_RPD` | `400` | Process-wide Geocoding calls per rolling day |
| `GEOCODE_COOLDOWN_SECONDS` | `60` | Skip Geocoding this long after `OVER_QUERY_LIMIT` |
| `EXTRACT_IP_PER_MINUTE` | `8` | Per-client extract cap |
| `EXTRACT_IP_PER_DAY` | `20` | Per-client extract cap |
| `GEOCODE_IP_PER_MINUTE` | `10` | Per-client geocode cap |
| `GEOCODE_IP_PER_DAY` | `80` | Per-client geocode cap |
| `DETECT_IP_PER_MINUTE` | `20` | Per-client detect cap |
| `DETECT_IP_PER_DAY` | `80` | Per-client detect cap |

### Frontend (`frontend/.env.local`, template in `frontend/.env.example`)

| Var | Purpose |
|-----|---------|
| `VITE_GOOGLE_MAPS_API_KEY` | Maps JavaScript API. Exposed to the browser by design. Restrict to HTTP referrers (`http://localhost:5173/*` and the Vercel origin). Never commit the real value. |
| `VITE_API_BASE_URL` | Render origin in production (`https://….onrender.com`), no trailing slash. Leave unset in Vite dev so `/api` uses the local proxy. |

API keys must never be committed. Gemini / Groq keys stay on the backend.
