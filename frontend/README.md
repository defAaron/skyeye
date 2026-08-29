# SkyEye frontend

Vite + React + TypeScript testing UI for the SkyEye detection API. Plain CSS, no UI
framework, no map SDK.

## Run

```bash
npm install
npm run dev     # http://localhost:5173
```

The dev server proxies `/api/*` to the Flask backend at `http://127.0.0.1:5001`, so
leave `VITE_API_BASE_URL` unset locally. On Vercel, set it to the Render origin
(see [docs/deploy.md](../docs/deploy.md)). Start the backend separately or the
status panel will report the backend as unreachable.

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
├── api/client.ts            # typed fetch wrappers, contract error parsing
├── components/SafetyBanner  # non-dismissible disclaimer bar
├── types.ts                 # mirrors docs/api-contract.md
└── App.tsx                  # Detect page shell
```

`src/types.ts` mirrors [`docs/api-contract.md`](../docs/api-contract.md) and may only
change alongside it.

## Not yet implemented

Sample picker, upload, detection overlay, and the ranked results list land in a later
step. No secrets or API keys belong in this app.
