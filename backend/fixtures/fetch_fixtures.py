"""Download the demo corpus described by manifest.json.

Image blobs are gitignored, so a fresh clone needs this script:

    cd backend && venv/bin/python fixtures/fetch_fixtures.py

Sources are openly licensed Wikimedia Commons files resolved by title through
the Commons API, so nothing here depends on a hardcoded CDN path.
"""

from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "SkyEye-fixture-fetch/0.1 (RescueHacks SAR demo; contact via repo)"

FIXTURES_DIR = Path(__file__).resolve().parent
IMAGES_DIR = FIXTURES_DIR / "images"
MANIFEST = FIXTURES_DIR / "manifest.json"

REQUEST_SPACING_SECONDS = 4.0

# Commons rate-limits full originals hard and explicitly asks callers to use sized
# thumbnails instead. 3000px is also plenty for detection: subjects stay ~20-60px,
# and CPU tiled inference on a laptop finishes in a sane time.
TARGET_MAX_WIDTH = 3000


def _ssl_context() -> ssl.SSLContext:
    """python.org framework builds ship no system roots; certifi comes with the venv."""
    try:
        import certifi
    except ImportError:
        return ssl.create_default_context()
    return ssl.create_default_context(cafile=certifi.where())


def fetch(url: str, attempts: int = 5) -> bytes:
    """Commons rate-limits aggressively; back off instead of hammering it."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    context = _ssl_context()
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=120, context=context) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 503) or attempt == attempts - 1:
                raise
            time.sleep(15 * (attempt + 1))
    raise RuntimeError("unreachable")


def resolve_downloads(titles: list[str]) -> dict[str, str]:
    """Map Commons file title -> download URL, preferring a capped-width thumbnail."""
    urls: dict[str, str] = {}
    for start in range(0, len(titles), 20):
        batch = titles[start : start + 20]
        query = urllib.parse.urlencode(
            {
                "action": "query",
                "format": "json",
                "prop": "imageinfo",
                "iiprop": "url|size",
                "iiurlwidth": TARGET_MAX_WIDTH,
                "titles": "|".join(batch),
            }
        )
        payload = json.loads(fetch(f"{API}?{query}"))
        for page in payload.get("query", {}).get("pages", {}).values():
            info = (page.get("imageinfo") or [{}])[0]
            wider_than_target = (info.get("width") or 0) > TARGET_MAX_WIDTH
            url = info.get("thumburl") if wider_than_target else info.get("url")
            if url:
                urls[page["title"]] = url
        time.sleep(REQUEST_SPACING_SECONDS)
    return urls


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    samples = manifest["samples"]
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    pending = [s for s in samples if not (IMAGES_DIR / s["filename"]).is_file()]
    if not pending:
        print(f"All {len(samples)} fixtures already present in {IMAGES_DIR.name}/.")
        return 0

    urls = resolve_downloads([s["commons_title"] for s in pending])

    failures = 0
    mismatches = []
    for sample in pending:
        title = sample["commons_title"]
        url = urls.get(title)
        if not url:
            print(f"FAIL  {sample['id']}: could not resolve {title}")
            failures += 1
            continue
        target = IMAGES_DIR / sample["filename"]
        try:
            target.write_bytes(fetch(url))
        except (urllib.error.URLError, OSError) as exc:
            print(f"FAIL  {sample['id']}: {exc}")
            failures += 1
            continue

        size_mb = target.stat().st_size / 1_000_000
        actual = _dimensions(target)
        note = ""
        if actual and (actual[0], actual[1]) != (sample["width"], sample["height"]):
            note = f"  [manifest says {sample['width']}x{sample['height']}]"
            mismatches.append(sample["id"])
        shape = f"{actual[0]}x{actual[1]}" if actual else "unknown"
        print(f"ok    {sample['id']:24s} {shape:>10s} {size_mb:5.1f} MB{note}")
        time.sleep(REQUEST_SPACING_SECONDS)

    print(f"\n{len(pending) - failures}/{len(pending)} downloaded, {failures} failed.")
    if mismatches:
        print(f"Dimension mismatch vs manifest: {', '.join(mismatches)}")
    return 1 if failures else 0


def _dimensions(path: Path) -> tuple[int, int] | None:
    try:
        from PIL import Image

        with Image.open(path) as image:
            return image.width, image.height
    except Exception:
        return None


if __name__ == "__main__":
    raise SystemExit(main())
