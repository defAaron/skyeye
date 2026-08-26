# SkyEye

AI-assisted missing person search & rescue tool for **RescueHacks** (Emergency Response / Community Rescue track).

SkyEye compresses the SAR triage pipeline: a caller describes what they know in plain language, an LLM extracts structured facts, and a vision model scans available overhead imagery for human-shaped candidates — returning ranked coordinates for human responders to verify.

> **SkyEye does not replace SAR teams, dispatchers, or law enforcement.** It is a triage accelerant that narrows "where do we look first" from hours to minutes. Every output is a *lead to verify*, not a confirmed location.

## Documentation

- [PRD & TRD](./docs/PRD_TRD.md) — full product and technical requirements (imported from Notion)

## Source

Original spec: [SkyEye_PRD_TRD on Notion](https://app.notion.com/p/3c88fa97c148804c9477c3feca09cefb)

## Stack (planned)

| Layer | Tool |
|-------|------|
| Frontend | React + Google Maps JS API |
| Backend | Flask (`/api/extract`, `/api/geocode`, `/api/detect`) |
| LLM | Gemini 2.0 Flash (Groq Llama 3.1 fallback) |
| Detection | YOLOv8 (Ultralytics) |
| Geocoding | Google Maps Geocoding API |
