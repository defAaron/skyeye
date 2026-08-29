# Deploy SkyEye (Vercel UI + Render API)

This is the **shipped** topology. The browser talks to Render **directly**. Do not
proxy `/api` through Vercel: Hobby rewrites time out around 10 seconds, and
tiled CPU detect routinely needs tens of seconds (the client already waits up
to 180s).

## What you need

| Piece | Where | Notes |
|-------|--------|--------|
| Vite + React UI | **Vercel** | Root Directory = `frontend` |
| Flask + YOLOv8n ONNX | **Render** web service | Docker. ONNX Runtime (no PyTorch in the running image) |
| Maps JS key | Vercel env | HTTP referrer restriction includes the Vercel origin |
| Geocoding + Gemini/Groq keys | Render env | Server-side only. Never put these on Vercel |

The running image does **not** install PyTorch. Weights are exported to
`yolov8n.onnx` at build time. That is what keeps detect under Render's memory
cap (status 137 was the OOM killer loading `torch` + Ultralytics).

Render's free instance still spins down. A cold start then downloads nothing
(weights and fixtures are baked into the image) but the first detect still
warms the ONNX session.

## 1. Render API

1. New → Web Service → this repo.
2. Runtime **Docker**.
   - **Root Directory:** leave blank (repo root)
   - **Dockerfile Path:** `backend/Dockerfile`
   - **Docker Build Context:** `.` (repo root — Render’s default)
   Or apply the repo-root [render.yaml](../render.yaml) Blueprint.
3. Plan **Standard** (`standard` / `1c-2g`), not Free.
4. Health check path: `/api/health`.
5. Environment (dashboard, not git):

| Var | Value |
|-----|--------|
| `TRUST_PROXY` | `1` |
| `CORS_ORIGIN` | Your Vercel origin, e.g. `https://skyeye.vercel.app` (no trailing slash). Comma-separate if you also use a custom domain. |
| `CORS_ORIGIN_REGEX` | Optional. `https://.*\.vercel\.app` allows preview deploys. Omit if you want production only. |
| `GOOGLE_MAPS_API_KEY` | Server Geocoding key |
| `GEMINI_API_KEY` | Google AI Studio key |
| `GROQ_API_KEY` | Optional fallback |

The first Docker build pulls a CPU torch wheel, YOLOv8n weights, and the ~32 MB
fixture corpus. Expect 10–15 minutes.

Confirm with:

```bash
curl -sS https://YOUR-SERVICE.onrender.com/api/health
```

`status` should be `"ok"`. `model.loaded` stays `false` until the first detect.
`model.weights` is `yolov8n.onnx`.

## 2. Vercel frontend

1. New Project → this repo.
2. **Root Directory:** `frontend`.
3. Framework: Vite. Build `npm run build`, output `dist`.
4. Environment:

| Var | Value |
|-----|--------|
| `VITE_API_BASE_URL` | `https://YOUR-SERVICE.onrender.com` (no trailing slash, no `/api` suffix) |
| `VITE_GOOGLE_MAPS_API_KEY` | Maps JavaScript API key |

`frontend/vercel.json` rewrites `/app` to `index.html` so the console route
works. Leave `VITE_API_BASE_URL` unset in local `.env.local` so Vite keeps
proxying `/api` to `http://127.0.0.1:5001`.

## 3. Google Cloud key restrictions

After both URLs exist:

- **Browser key** (`VITE_GOOGLE_MAPS_API_KEY`): HTTP referrers
  `http://localhost:5173/*` and `https://YOUR-VERCEL-DOMAIN/*` (the trailing
  `/*` is required). Enable **Maps JavaScript API** and billing. A key that
  only allows Geocoding will geocode from Render and still show Google's
  "This page didn't load Google Maps correctly" overlay in the browser.
- **Server key** (`GOOGLE_MAPS_API_KEY` on Render): restrict to the Geocoding
  API. IP restriction is optional; Render egress IPs are not fixed on every plan.

Redeploy the Vercel project after changing `VITE_*` values — they are baked in
at build time.

## 4. Smoke the live pair

```bash
# From a machine that can reach Render
curl -sS https://YOUR-SERVICE.onrender.com/api/health
backend/venv/bin/python scripts/smoke.py --base-url https://YOUR-SERVICE.onrender.com
```

Then open the Vercel URL:

1. Landing (`/`) loads; **Open console** goes to `/app`.
2. Console health chip is online (not a port-5001 network error).
3. Extract the prefilled report → map ring appears.
4. Detect on `Single person lying on a lawn` — first run may take a while
   while the model warms. Later runs should land in tens of seconds.
5. True-negative fixture still returns zero candidates.

## What this build does not include

- No Vercel rewrite of `/api` → Render (timeout).
- No change to `/api/detect` request/response shape.
- No video upload, globe-as-product, or satellite-tile detect.
- No commit of `.env`, keys, weights, or fixture image blobs.
