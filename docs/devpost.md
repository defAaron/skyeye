# SkyEye

**Hours of searching. Minutes to a lead.** SkyEye spots people in drone photos so rescue teams know where to look first.

---

## Inspiration

The first hours after someone goes missing matter most, and they are messy. A caller is scared, the report is unstructured, and the search area starts as a guess. If a drone goes up, someone still has to scan every frame for a person-shaped speck in trees, water, or trail.

I built SkyEye for **RescueHacks** (Emergency Response / Community Rescue). “Run YOLO on a satellite map” fails in thirty seconds with a GIS-literate judge. Commercial satellite imagery tops out around $30$ to $50\,\text{cm}$ per pixel. From nadir, a person is about half a metre across:

$$
n_{\text{pixels}} \approx \frac{w_{\text{person}}}{\text{GSD}} \approx \frac{0.5\,\text{m}}{0.4\,\text{m/px}} \approx 1\text{ to }2
$$

A detector has nothing to find. That constraint became the product: **decouple where to look from what to look at.** Maps and Lost Person Behavior size the ring. Detection runs only on drone-altitude photographs, the altitude real SAR drones fly.

The other spark was Robert Koester’s **Lost Person Behavior** tables. Real teams size a ring from subject category and time. A simplified version of that in the demo beats a generic “AI finds missing people” wrapper.

SkyEye is a triage accelerant for SAR teams, dispatch, and police. Every output is a *lead to verify*.

---

## What it does

SkyEye is two loops that meet on a map.

**1. Report → search area**

A bystander or coordinator types what they know in plain language (“Dad, 70, red jacket, Bruce Trail near Milton, last seen around 3pm”). Gemini Flash (Groq as fallback) extracts structured facts: last-known place, elapsed hours, clothing, and a subject category. Google Geocoding turns the place into $\text{lat}/\text{lng}$. A simplified 50th-percentile Lost Person Behavior table sizes the ring:

$$
r = \operatorname{clamp}\!\left(r_{50}\sqrt{\frac{t}{t_0}},\; 200\,\text{m},\; 8000\,\text{m}\right),\qquad t_0 = 3\,\text{h}
$$

$\sqrt{t}$ keeps the ring from doubling when time doubles. An elderly hiker at $4.5\,\text{h}$ gets $r = 1347\,\text{m}$ from the table.

**2. Drone photo → ranked candidates**

A wilderness photograph goes through sliding-window YOLOv8n (ONNX). Boxes are merged across tiles, scored, and projected onto the map as pins when the fixture is georeferenced. The operator reviews them. The UI never says “found.”

A non-dismissible banner stays on every result: SkyEye surfaces possible leads only. Contact 911 / local SAR immediately. Leave the pin to responders.

---

## How I built it

| Layer | Choice |
|---|---|
| API | Flask: `/api/extract`, `/api/geocode`, `/api/detect`, `/api/samples`, `/api/health` |
| Detection | YOLOv8n ONNX Runtime, tiled inference + IoU/containment merge |
| Intake | Gemini Flash primary, Groq GPT-OSS 20B fallback, typed JSON |
| Where | Google Geocoding (server) + Maps JS (`@vis.gl/react-google-maps`) |
| Radius | Simplified LPB 50th-percentile table |
| UI | Vite + React + TypeScript; landing + operator console at `/app` |
| Demo corpus | 8 openly licensed Wikimedia Commons drone photos |
| Deploy | Vercel (UI) + Render Docker (API). Detect goes straight to Render, past Vercel’s Hobby timeout. |

Aerial people are a few dozen pixels tall. One downscaled pass loses them, so the image is cut into overlapping tiles of edge $T$ and overlap $\rho$:

$$
s = T\,(1-\rho)
$$

Each tile is letterboxed to the network’s native input. Detections project back to full-image space, then merge. `TILE_SIZE` is a recall lever. On a controlled scale test, $T=320$ lifted recall from $4/10$ to $7/10$, at about $2.5\times$ latency and $5\times$ the false positives.

Demo wilderness fixtures sit on the Bruce Trail / Milton conservation area so pins can be reviewed on a real map. The UI labels them as demo-placed.

---

## Challenges I ran into

**Satellite GSD.** The obvious demo is “drop a pin, scan the basemap.” That is physically impossible at commercial GSD. The detector never runs on map tiles.

**COCO priors on aerial subjects.** Pretrained YOLOv8n has a hard floor around $60\,\text{px}$. Subjects $\ge 100\,\text{px}$ tall are reliable. Subjects $\le 60\,\text{px}$ are missed entirely; the model never sees them. Dropping confidence to $0.05$ recovered none of them and added nine false positives. HERIDAL-class drone imagery puts a person at roughly $30$ to $60\,\text{px}$. That is the gap.

**Pose failures.** One fixture, `lone_surfer_shorebreak`, never detects at any threshold. A person lying prone on a board, seen from directly above, misses COCO’s upright-person prior. Tiling cannot fix it. I kept the miss in the corpus on purpose.

**Production memory.** PyTorch on a 2 GB Render box died with status $137$. The fix was architectural: never import `torch` at runtime, bake an ONNX export into the Docker image, run ONNX Runtime, one Gunicorn worker, `TORCH_NUM_THREADS=1`. The operator needed a Docker rebuild.

**Honest demo geography.** Pins on a familiar trail invite the question: “was this photo taken there?” Labeling demo-placement in the UI bought credibility.

---

## Accomplishments that I'm proud of

- **7 of 8 demo fixtures behave as expected.** Both true-negative fixtures (conifer canopy, closed broadleaf) return zero false positives.
- **Time-to-first-lead.** Slowest fixture is about $5$ to $8\,\text{s}$ on a laptop CPU, inside the $30\,\text{s}$ PRD target.
- **Measured limits in the README.** A $60\,\text{px}$ floor, a known pose miss, and a tiling tradeoff with real numbers.
- **Safety in the UI.** Explicit confidence, no “found” copy, persistent emergency banner, keys kept out of responses and logs.
- **A deploy that runs detection.** ONNX on Render, Maps + extract on the live console, API contract frozen so the shape stays put mid-build.

---

## What I learned

Remote sensing has a resolution floor you cannot prompt around. SAR has a literature (Koester / LPB) that beats a default radius. Small-object detection is a tiling and prior problem. A 2 GB container will OOM a full PyTorch stack even when the model is “tiny.”

The most important line in a rescue tool refuses certainty. Ranked leads with scores beat a green checkmark.

---

## What's next for SkyEye

- **Aerial fine-tune** on HERIDAL / SARD so the model’s prior matches drone nadir: prone, partial, 30 to 60 px.
- **Video / live drone ingest:** per-frame detection on footage SAR teams already fly. Out of scope for this build; the obvious next loop.
- **Thermal / IR** for night search, when most misses happen.
- **A volunteer SAR pilot** with a chapter that already owns drones and still reviews footage by hand.

Detection stays on drone photos. The map sizes the search area.
