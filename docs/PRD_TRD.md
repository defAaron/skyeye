# SkyEye — PRD & TRD

### AI-Assisted Missing Person Search & Rescue Tool

**Hackathon:** RescueHacks | **Track:** Emergency Response / Community Rescue

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
2. LLM EXTRACTION (Gemini, free tier)
   Structured JSON out:
   { location_text, approx_time_last_seen, elapsed_hours,
     description: {age, clothing, distinguishing_features},
     terrain_hint, urgency_flags }
        │
        ▼
3. GEOCODE + SEARCH RADIUS
   location_text → lat/lng (Google Maps Geocoding API)
   elapsed_hours → search radius (Lost Person Behavior heuristic,
   see 1.5) → bounding box drawn on map
        │
        ▼
4. IMAGERY RETRIEVAL
   Pull the best available overhead imagery for that bounding box
   (see TRD 2.3 for the resolution caveat — this is the one part
   of the pipeline that needs an honest workaround)
        │
        ▼
5. DETECTION
   YOLOv8 model (fine-tuned on aerial person-detection datasets)
   scans imagery → bounding boxes + confidence scores for
   candidate human shapes
        │
        ▼
6. FUSION + OUTPUT
   Detections re-projected onto the map as pins, sorted by
   confidence + proximity to last known location.
   UI returns:
   "3 candidate sightings found near [area]. Highest-confidence
    match: 340m NE of last known location (confidence 0.78).
    Contact SAR / 911 to verify before approaching."
```

### 1.4 Core Features (MVP for hackathon demo)

| # | Feature | Priority |
|---|---------|----------|
| 1 | Free-text intake box → LLM structured extraction | Must-have |
| 2 | Geocoded map view centered on last known location | Must-have |
| 3 | Search radius overlay based on elapsed time | Must-have |
| 4 | Object detector run against demo aerial imagery, bounding boxes shown | Must-have |
| 5 | Ranked candidate list with confidence + distance | Must-have |
| 6 | "Contact emergency services" persistent banner (safety requirement) | Must-have |
| 7 | Live drone feed ingestion (upload video, run detection per frame) | Stretch |
| 8 | Multi-report clustering (multiple witnesses → merged search area) | Stretch |

### 1.5 A Real Technique Worth Citing in Your Demo

Real SAR teams use **Lost Person Behavior (Koester methodology)** — statistical distance-traveled tables based on subject category (hiker, child, elderly, hunter, person with dementia, etc.) and terrain, to size a search ring instead of guessing. Baking a simplified version of this into your radius calculation (rather than a flat "500m circle") is a small addition that meaningfully raises your **Problem & Impact** and **Creativity** score — it shows you researched how real SAR actually works, not just how to run YOLO on an image.

### 1.6 Safety & Responsible Design (hackathon requirement)

- Every result screen carries a non-dismissible banner: *"SkyEye surfaces possible leads only. It does not confirm a person's location or safety. Contact 911 / local SAR immediately."*
- No feature suggests the user should personally go investigate a detection.
- Confidence scores are shown explicitly (never a bare "found!" claim) to avoid false certainty.
- All demo imagery/datasets are pre-existing public research data — no live surveillance claims.

### 1.7 Success Metrics (for judges' "Future Potential")

- Detection recall on a held-out slice of the aerial SAR dataset (be ready to state a real number from your validation set).
- Time-to-first-lead: report submitted → first ranked candidate shown (target: under 30 seconds in demo).
- Post-hackathon path: partnership pilot with a volunteer SAR org that already flies drones but reviews footage manually — this is your "beyond the hackathon" answer.

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
       │            │  /api/detect     │────▶│  YOLOv8 (PyTorch,    │
       │            │                  │     │  local inference)    │
       │            └──────────────────┘     └─────────────────────┘
       │                     │
       ▼                     ▼
┌──────────────────────────────────────────────┐
│  Map view (Google Maps JS API) + result list  │
└──────────────────────────────────────────────┘
```

### 2.2 Exact Tooling (free-tier only, as requested)

| Layer | Tool | Why / Free-tier notes |
|-------|------|----------------------|
| LLM extraction | **Gemini 2.0 Flash** via Google AI Studio API | Free tier (as of this writing) gives generous per-minute/per-day request limits — plenty for a hackathon demo. Use `responseSchema` / JSON mode so extraction is a typed object, not free text you have to re-parse. |
| LLM fallback | **Groq API — Llama 3.1 8B Instant** | Fully free, extremely low latency. Keep as a fallback call if Gemini's free quota gets hit mid-demo (judges will not wait for a retry). |
| Geocoding | **Google Maps Geocoding API** | Google Cloud's free monthly credit covers hackathon-scale usage; converts your extracted `location_text` into lat/lng. |
| Map rendering | **Google Maps JavaScript API** (`@react-google-maps/api`) | Matches your React stack; free tier is sufficient for a demo. |
| Object detection model | **YOLOv8n or YOLOv8s (Ultralytics, open-source)** | Free, runs locally on CPU for small demo images, fine-tunable in a Colab notebook for free on their GPU tier. |
| Aerial person-detection training data | **HERIDAL dataset** or **SARD (Search And Rescue Dataset)** or **C2A (disaster victim aerial dataset)** | Free, public, purpose-built for exactly this task — drone-altitude imagery with labeled human bounding boxes. |
| Backend | **Flask** (matches your existing stack) | Simple `/extract`, `/geocode`, `/detect` endpoints. |
| Frontend | **React** (matches your existing stack) | Reuse patterns from your personal site / hackathon web editor project. |

### 2.3 Critical Technical Constraint — Read This Before You Build

Be precise about this in your pitch, because a judge with any GIS background will ask about it, and getting ahead of it is a **credibility win**, not a weakness to hide:

**Google Maps satellite/static imagery cannot resolve a person.** Commercial satellite imagery tops out around 30–50cm/pixel resolution even in the best cases, and Google's static tiles are generally coarser. A person is roughly the size of 1–2 pixels at that resolution — a YOLO model has nothing to detect. This is a real, well-known limit in the remote-sensing field, not a bug in your implementation.

**The fix (and it's a good one):** decouple "where to look" from "what to look at."

- Use **Google Maps** for what it's actually good at: geocoding, drawing the search radius, and giving the user a clean, familiar map UI to navigate.
- Use **drone-altitude imagery** (from HERIDAL/SARD/C2A, or an uploaded video for the stretch feature) for the actual detection step — this is the altitude those datasets and real SAR drones operate at, and where YOLO-style detection genuinely works.
- Frame this explicitly in your demo: *"SkyEye pinpoints the search area from a report, then runs detection on the closest available aerial/drone imagery for that area — not on satellite tiles, which don't have the resolution to resolve a person."* This is more accurate than most hackathon SAR pitches and will read as rigor, not limitation.
- For the live demo itself, simulate the "drone flyover" using pre-recorded footage tagged to a plausible location — a completely standard hackathon demo technique, and safe to disclose plainly to judges.

### 2.4 Data Flow — Request/Response Shapes

**`POST /api/extract`**

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

**`POST /api/geocode`** → `{ "lat": 43.49, "lng": -79.93, "radius_m": 1400 }`

(radius derived from `elapsed_hours` + `category` via a simplified Lost Person Behavior lookup table)

**`POST /api/detect`** → array of `{ "bbox": [...], "confidence": 0.78, "lat": ..., "lng": ... }`, sorted descending by confidence.

### 2.5 Suggested Build Order (for a hackathon timeline)

1. Hardcode a sample report → verify Gemini extraction JSON is reliable and typed correctly.
2. Wire geocoding + map rendering with a static pin (no detection yet) — get the UI demo-able early.
3. Get YOLOv8 running locally against a few HERIDAL/SARD sample images — validate detection works before touching the pipeline.
4. Connect detection output back onto the map as pins.
5. Polish: confidence sorting, the safety banner, and a clean "type a report → see results" demo path.
6. If time remains: stretch feature (video upload → per-frame detection).

### 2.6 Post-Hackathon Path (for "Future Potential" scoring)

- Real drone integration (DJI SDK or similar) instead of static datasets.
- Fine-tune detection on infrared/thermal drone footage for night search capability — the single highest-impact real-world upgrade, since most SAR misses happen after dark.
- Partnership pilot with a volunteer SAR chapter that already owns drones.
