# SkyEye frontend

Vite + React + TypeScript. Plain CSS. Two routes from `src/Root.tsx`:

| Path | What |
|------|------|
| `/` | Landing (`src/landing/`). Decorative Three.js globe — not a search surface. |
| `/app` | Operator console (`src/App.tsx`). Report intake, LPB ring, map, detect. |

`frontend/vercel.json` rewrites `/app` to `index.html` so the console works on Vercel.

## Run

```bash
cp .env.example .env.local
# VITE_GOOGLE_MAPS_API_KEY — Maps JS, restrict to http://localhost:5173/*
# Leave VITE_API_BASE_URL unset so Vite proxies /api → Flask :5001
npm install
npm run dev     # http://localhost:5173
```

Start the backend separately or the console status panel reports it unreachable. Production: set `VITE_API_BASE_URL` to the Render origin (no trailing slash) and rebuild — see [docs/deploy.md](../docs/deploy.md).

## Scripts

| Script | Does |
|--------|------|
| `npm run dev` | Dev server on port 5173 with the `/api` proxy |
| `npm run build` | Typecheck (`tsc -b`) then production build |
| `npm run lint` | Oxlint |
| `npm run preview` | Serve the production build |

## Layout

```
src/
├── Root.tsx                 # `/` vs `/app`
├── App.tsx                  # Console shell
├── main.tsx
├── types.ts                 # mirrors docs/api-contract.md
├── api/client.ts            # typed fetch, 180s detect abort, VITE_API_BASE_URL
├── landing/                 # LandingPage, GlobeScene
├── lib/                     # geo, format, errorCopy
└── components/
    ├── SafetyBanner         # non-dismissible contract disclaimer
    ├── ReportIntake         # POST /api/extract
    ├── SearchArea           # POST /api/geocode + LPB fields
    ├── SearchMap            # @vis.gl/react-google-maps
    ├── DetectPanel          # samples, upload, detect
    ├── SamplePicker
    ├── UploadZone           # JPEG/PNG only
    ├── DetectionOverlay
    └── DetectionList
```

`src/types.ts` mirrors [`docs/api-contract.md`](../docs/api-contract.md) and may only change alongside it.

Gemini / Groq / Geocoding keys stay on the backend. The only frontend secret-shaped value is the **Maps JavaScript** key, which Google expects in the browser. Restrict it to HTTP referrers.
