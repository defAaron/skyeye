# SkyEye — PRD & TRD

### AI-Assisted Missing Person Search & Rescue Tool

**Hackathon:** RescueHacks | **Track:** Emergency Response / Community Rescue

**Status (August 2026):** this is the **shipped hackathon product**, not a backlog. Landing at `/`, operator console at `/app`, extract → geocode → LPB ring → tiled YOLOv8n **ONNX** detect, Vercel UI + Render API. Stretch items (video ingest, multi-report clustering, HERIDAL fine-tune, globe-as-product) are **not** in the build. Frozen HTTP shapes: [api-contract.md](api-contract.md). Post-hackathon path: [skyeye-next-steps.pdf](skyeye-next-steps.pdf).

---

## PART 1 — PRODUCT REQUIREMENTS DOCUMENT (PRD)

### 1.1 Problem Statement

When a person goes missing, the first hours are the most critical — but the initial report process (calling it in, describing the person, guessing where to look) is slow, unstructured, and depends entirely on how well a distressed caller can communicate under stress. Search & rescue (SAR) teams then have to manually interpret that report, define a search area, and — if aerial imagery is available — visually scan footage for a person, frame by frame.

SkyEye compresses that pipeline: a caller describes what they know in plain language, an LLM extracts the structured facts SAR teams actually need, and a vision model scans available overhead imagery for human-shaped candidates in the likely search radius — returning a ranked list of coordinates a human responder can immediately verify.

**SkyEye does not replace SAR teams, dispatchers, or law enforcement.** It is a triage accelerant: it narrows "where do we look first" from hours to minutes. Every output is explicitly framed as a *lead to verify*, not a confirmed location, and the UI always instructs the user to contact emergency services / local SAR immediately.

### 1.2 Target Users

- **Primary demo persona:** a family member or bystander who has already called 911/local authorities and wants to give searchers a head start, or a SAR volunteer coordinator triaging multiple leads at once.
- **Real-world adopter (future potential):** volunteer SAR organizations (e.g., mountain rescue, coastal/wilderness SAR), who already use drone footage but review it manually.

### 1.3 User Flow

```
1. INTAKE
   User types a free-text report:
   "My dad went missing around 3pm near Bruce Trail, Milton.
    He's 70, wearing a red jacket, last seen walking near the
    conservation area entrance."
        │
        ▼
2. LLM EXTRACTION (Gemini Flash, Groq GPT-OSS fallback)
   Structured JSON out:
   { location_text, time_last_seen, elapsed_hours,
     subject: {age, clothing, distinguishing_features, category},
     terrain_hint }
        │
        ▼
3. GEOCODE + SEARCH RADIUS
   location_text → lat/lng (Google Maps Geocoding API)
   elapsed_hours → search radius (Lost Person Behavior heuristic,
   see 1.5) → bounding box drawn on map
        │
        ▼
4. IMAGERY
   Operator picks a demo fixture or uploads a JPEG/PNG drone photograph.
   Map / satellite tiles are never detector input (see TRD 2.3).
        │
        ▼
5. DETECTION
   YOLOv8n (ONNX Runtime, sliding-window tiles) scans the photograph →
   bounding boxes + confidence scores for candidate human shapes
        │
        ▼
6. FUSION + OUTPUT
   Detections as boxes on the photograph and pins on the ring when the
   fixture is georeferenced, sorted by confidence. Distance from last-known
   when both points exist. The UI never says "found." Zero candidates is
   not "the area is clear." Contact 911 / local SAR immediately.
```

### 1.4 Core Features (hackathon demo — shipped)

| # | Feature | Status |
|---|---------|--------|
| 1 | Free-text intake box → LLM structured extraction | Shipped (`/api/extract`) |
| 2 | Geocoded map view centered on last known location | Shipped (Maps JS) |
| 3 | Search radius overlay based on elapsed time | Shipped (simplified LPB) |
| 4 | Object detector on demo aerial imagery + upload, bounding boxes shown | Shipped (tiled YOLOv8n ONNX) |
| 5 | Ranked candidate list with confidence + distance when georeferenced | Shipped |
| 6 | "Contact emergency services" persistent banner (safety requirement) | Shipped (console + landing footer) |
| 7 | Live drone feed ingestion (upload video, run detection per frame) | Out of scope this build |
| 8 | Multi-report clustering (multiple witnesses → merged search area) | Out of scope this build |

### 1.5 A Real Technique Worth Citing in Your Demo

Real SAR teams use **Lost Person Behavior (Koester methodology)** — statistical distance-traveled tables based on subject category (hiker, child, elderly, hunter, person with dementia, etc.) and terrain, to size a search ring instead of guessing. Baking a simplified version of this into your radius calculation (rather than a flat "500m circle") is a small addition that meaningfully raises your **Problem & Impact** and **Creativity** score — it shows you researched how real SAR actually works, not just how to run YOLO on an image.

### 1.6 Safety & Responsible Design (hackathon requirement)

- Non-dismissible banner on the console (same copy in the landing footer): *"SkyEye surfaces possible leads only. It does not confirm a person's location or safety. Contact 911 / local SAR immediately."*
- No feature suggests the user should personally go investigate a detection.
- Confidence scores are shown explicitly (never a bare "found!" claim) to avoid false certainty.
- All demo imagery/datasets are pre-existing public research data — no live surveillance claims.

### 1.7 Success Metrics (demo, as shipped)

- Time-to-first-lead: under 30 s target. Slowest demo fixture is about 5–8 s on a laptop CPU.
- 7 of 8 demo fixtures behave as expected; both true-negative canopy fixtures return zero false positives.
- Measured detector floor: pretrained YOLOv8n misses subjects ≤60 px; `lone_surfer_shorebreak` is a permanent pose miss. Quote those, do not paper over them.
- Post-hackathon path: partnership pilot with a volunteer SAR org that already flies drones but reviews footage manually — see [skyeye-next-steps.pdf](skyeye-next-steps.pdf).

---

## PART 2 — TECHNICAL REQUIREMENTS DOCUMENT (TRD)

### 2.1 Architecture Overview

```
┌────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│  Frontend  │────▶│  Backend (Flask)  │────▶│  Gemini API (free)  │
│  (React)   │     │   /api/extract    │     │  structured JSON    │
└────────────┘     └──────────────────┘     └─────────────────────┘
       │                     │
       │                     ▼
       │            ┌──────────────────┐     ┌─────────────────────┐
       │            │  /api/geocode    │────▶│ Google Maps Geocoding│
       │            └──────────────────┘     │ API                  │
       │                     │               └─────────────────────┘
       │                     ▼
       │            ┌──────────────────┐     ┌─────────────────────┐
       │            │  /api/detect     │────▶│  YOLOv8n ONNX Runtime │
       │            │                  │     │  (no PyTorch in proc)  │
       │            └──────────────────┘     └─────────────────────┘
       │                     │
       ▼                     ▼
┌──────────────────────────────────────────────┐
│  Map view (Google Maps JS API) + result list  │
└──────────────────────────────────────────────┘
```

### 2.2 Tooling (as shipped)

| Layer | Tool | Why / Free-tier notes |
|-------|------|----------------------|
| LLM extraction | **Gemini Flash** via Google AI Studio (`gemini-3.6-flash`, then 3.5-lite / 3.5 / 3.1-lite, then `gemini-flash-latest`) | Typed JSON. Gemini 2.0 Flash is retired. |
| LLM fallback | **Groq — `openai/gpt-oss-20b`**, then `openai/gpt-oss-120b` | Llama 3.1 Instant is shut down on Groq free/developer tiers (Aug 2026). |
| Geocoding | **Google Maps Geocoding API** | Server-side. Key never in the browser or in JSON. |
| Map rendering | **Google Maps JavaScript API** (`@vis.gl/react-google-maps`) | Browser key, HTTP-referrer restricted. |
| Object detection | **YOLOv8n ONNX Runtime** | Tiled inference. Production image has no PyTorch. |
| Aerial person-detection training data | **Not used in this build.** Demo corpus is 8 Wikimedia Commons drone photos. HERIDAL / SARD / C2A remain request-gated. | Fine-tune is post-hackathon. |
| Backend | **Flask** | `/api/extract`, `/api/geocode`, `/api/detect`, `/api/samples`, `/api/health`. |
| Frontend | **Vite + React + TypeScript** | `/` landing, `/app` console. |
| Deploy | **Vercel** (UI) + **Render Docker** (API) | Browser calls Render directly. |

### 2.3 Critical technical constraint

Be precise about this in the demo: a judge with any GIS background will ask, and getting ahead of it is a **credibility win**.

**Google Maps satellite/static imagery cannot resolve a person.** Commercial satellite imagery tops out around 30–50cm/pixel. A person is roughly 1–2 pixels — a detector has nothing to find. This is a remote-sensing limit, not a bug.

**What shipped:** decouple "where to look" from "what to look at."

- **Google Maps** geocodes, draws the LPB ring, and shows pins. Never scanned.
- **Detection** runs on drone-altitude JPEG/PNG (demo fixtures or upload). HERIDAL/SARD were not used (gated). Video ingest was not shipped.
- Demo flyovers on the Bruce Trail / Milton conservation area are **labeled demo-placement** — those photographs were not captured there.

### 2.4 Data flow — request/response shapes

Canonical shapes: [api-contract.md](api-contract.md). Summary:

**`POST /api/extract`** — `provider` is `"gemini"` or `"groq"`; `disclaimer` is always present. Extract does not geocode.

```json
// Request
{ "report_text": "My dad went missing around 3pm near..." }

// Response (Gemini structured output)
{
  "location_text": "Bruce Trail, Milton",
  "time_last_seen": "15:00",
  "elapsed_hours": 4.5,
  "subject": {
    "age": 70,
    "clothing": "red jacket",
    "distinguishing_features": "walks with a cane",
    "category": "elderly_hiker"
  },
  "terrain_hint": "wooded trail"
}
```

**`POST /api/geocode`** → `{ lat, lng, formatted_address, radius_m, category, elapsed_hours, lpb_note }`

(radius derived from `elapsed_hours` + `category` via a simplified Lost Person Behavior lookup table)

**`POST /api/detect`** → `{ detections: [{ id, bbox_xyxy, confidence, class_name, lat, lng }], meta, disclaimer }`, sorted by confidence descending. `lat`/`lng` are null for uploads.

### 2.5 Build order (completed)

1. Typed Gemini/Groq extract JSON.
2. Geocoding + Maps JS ring (no detection).
3. YOLOv8n ONNX against the Wikimedia demo corpus — not HERIDAL (gated).
4. Detection pins on the map for georeferenced fixtures (demo-placement labeled).
5. Safety banner, ranked list, landing + `/app`.
6. Vercel + Render. Video upload was not shipped.

### 2.6 Post-hackathon path

Unchanged in intent; not in this repo's current scope:

- Fine-tune on HERIDAL/SARD.
- Video / live drone ingest (DJI SDK or similar).
- Infrared/thermal for night search.
- Partnership pilot with a volunteer SAR chapter that already owns drones.

Details: [skyeye-next-steps.pdf](skyeye-next-steps.pdf).
