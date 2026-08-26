"""End-to-end smoke test for the SkyEye core loop.

Run against a live backend (defaults to the dev port):

    backend/venv/bin/python scripts/smoke.py
    backend/venv/bin/python scripts/smoke.py --base-url http://127.0.0.1:5001

Checks the contract in docs/api-contract.md: health, sample listing, sample image
serving, error handling, and detection on both an obvious-person fixture and a
true negative. Exits non-zero if any check fails.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import struct
import sys
import time
import urllib.error
import urllib.request
import uuid
import zlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_IMAGES = REPO_ROOT / "backend" / "fixtures" / "images"

PASS = "PASS"
FAIL = "FAIL"


class Report:
    def __init__(self) -> None:
        self.rows: list[tuple[str, str, str]] = []

    def add(self, ok: bool, name: str, detail: str = "") -> bool:
        self.rows.append((PASS if ok else FAIL, name, detail))
        marker = "\u2713" if ok else "\u2717"
        print(f"  {marker} {name}" + (f" — {detail}" if detail else ""))
        return ok

    @property
    def failures(self) -> int:
        return sum(1 for status, _, _ in self.rows if status == FAIL)


def get_json(url: str, timeout: int = 30) -> tuple[int, dict]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        body = exc.read()
        try:
            return exc.code, json.loads(body)
        except json.JSONDecodeError:
            return exc.code, {"raw": body[:200].decode("utf-8", "replace")}
    except urllib.error.URLError as exc:
        return 0, {"error": {"code": "UNREACHABLE", "message": str(exc.reason)}}


def head(url: str, timeout: int = 60) -> tuple[int, str, int]:
    request = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
            return response.status, response.headers.get("Content-Type", ""), len(body)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers.get("Content-Type", ""), 0


def post_multipart(url: str, fields: dict, files: dict, timeout: int = 600):
    """Minimal multipart encoder so the smoke test needs no extra dependency."""
    boundary = f"----SkyEyeSmoke{uuid.uuid4().hex}"
    parts: list[bytes] = []

    for name, value in fields.items():
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'
            f"{value}\r\n".encode()
        )
    for name, path in files.items():
        path = Path(path)
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; '
            f'filename="{path.name}"\r\nContent-Type: {mime}\r\n\r\n'.encode()
        )
        parts.append(path.read_bytes())
        parts.append(b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())

    body = b"".join(parts)
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, {"raw": raw[:200].decode("utf-8", "replace")}
    except urllib.error.URLError as exc:
        return 0, {"error": {"code": "UNREACHABLE", "message": str(exc.reason)}}


def png_header_only(width: int, height: int) -> bytes:
    """Signature + IHDR + IEND: a tiny file declaring an enormous canvas.

    Used to prove the megapixel cap is enforced from the header, before a decode
    can allocate memory for the declared size.
    """

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IEND", b"")


def check_detection_shape(report: Report, label: str, payload: dict) -> bool:
    ok = True
    for key in ("image_width", "image_height", "detections", "meta", "disclaimer"):
        ok &= report.add(key in payload, f"{label}: response has '{key}'")
    if "detections" not in payload:
        return False

    for detection in payload["detections"][:3]:
        keys_ok = all(
            key in detection
            for key in ("id", "bbox_xyxy", "confidence", "class_name", "lat", "lng")
        )
        ok &= report.add(keys_ok, f"{label}: detection has all contract keys")
        ok &= report.add(
            detection.get("class_name") == "person",
            f"{label}: class_name is 'person'",
            str(detection.get("class_name")),
        )
        ok &= report.add(
            detection.get("lat") is None and detection.get("lng") is None,
            f"{label}: lat/lng are null this phase",
        )
        bbox = detection.get("bbox_xyxy") or []
        ok &= report.add(
            len(bbox) == 4
            and all(isinstance(v, int) for v in bbox)
            and bbox[0] < bbox[2]
            and bbox[1] < bbox[3]
            and bbox[2] <= payload["image_width"]
            and bbox[3] <= payload["image_height"],
            f"{label}: bbox is 4 ints inside the image",
            str(bbox),
        )
        break

    confidences = [d.get("confidence", 0) for d in payload["detections"]]
    ok &= report.add(
        confidences == sorted(confidences, reverse=True),
        f"{label}: sorted by confidence descending",
    )
    return ok


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:5001")
    parser.add_argument("--conf", default="0.25")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    report = Report()

    print("\n[1] Health")
    status, health = get_json(f"{base}/api/health")
    if not report.add(status == 200, "GET /api/health returns 200", str(status)):
        print("\nBackend unreachable. Start it with: cd backend && venv/bin/python app.py")
        return 1
    report.add(health.get("status") == "ok", "status is 'ok'")
    report.add("limits" in health, "limits block present")
    report.add(
        isinstance(health.get("model", {}).get("weights"), str),
        "model weights reported",
        str(health.get("model", {}).get("weights")),
    )

    print("\n[2] Samples")
    status, samples_payload = get_json(f"{base}/api/samples")
    report.add(status == 200, "GET /api/samples returns 200", str(status))
    samples = samples_payload.get("samples", [])
    report.add(len(samples) > 0, "at least one fixture available", f"{len(samples)} found")
    by_scenario: dict[str, list[dict]] = {}
    for sample in samples:
        by_scenario.setdefault(sample.get("scenario", "?"), []).append(sample)
    report.add("obvious_person" in by_scenario, "corpus has an obvious_person fixture")
    report.add("true_negative" in by_scenario, "corpus has a true_negative fixture")

    if samples:
        first = samples[0]
        status, content_type, size = head(f"{base}{first['image_url']}")
        report.add(status == 200, "sample image serves 200", str(status))
        report.add(content_type.startswith("image/"), "sample image content-type", content_type)
        report.add(size > 0, "sample image has bytes", f"{size / 1_000_000:.1f} MB")

    print("\n[3] Error handling")
    status, body = get_json(f"{base}/api/samples/definitely-not-a-sample/image")
    report.add(status == 404, "unknown sample id returns 404", str(status))
    report.add(
        body.get("error", {}).get("code") == "SAMPLE_NOT_FOUND",
        "error code is SAMPLE_NOT_FOUND",
        str(body.get("error", {}).get("code")),
    )
    status, body = post_multipart(f"{base}/api/detect", {}, {})
    report.add(status == 400, "detect with no input returns 400", str(status))
    report.add(
        body.get("error", {}).get("code") == "NO_IMAGE",
        "error code is NO_IMAGE",
        str(body.get("error", {}).get("code")),
    )
    if samples:
        status, body = post_multipart(
            f"{base}/api/detect", {"sample_id": samples[0]["id"], "conf": "5"}, {}
        )
        report.add(status == 400, "out-of-range conf returns 400", str(status))

    probe = Path("_smoke_decode_guard.png")
    probe.write_bytes(png_header_only(20000, 20000))
    try:
        started = time.perf_counter()
        status, body = post_multipart(f"{base}/api/detect", {}, {"image": probe})
        elapsed = time.perf_counter() - started
    finally:
        probe.unlink(missing_ok=True)
    report.add(
        status == 413 and body.get("error", {}).get("code") == "IMAGE_TOO_LARGE",
        "400MP header in a 45-byte file returns 413",
        f"{status} {body.get('error', {}).get('code')}",
    )
    report.add(
        elapsed < 5,
        "oversized image rejected from header, not decoded",
        f"{elapsed:.2f}s",
    )

    print("\n[4] Detection — obvious person")
    obvious = (by_scenario.get("obvious_person") or [None])[0]
    if obvious:
        started = time.perf_counter()
        status, payload = post_multipart(
            f"{base}/api/detect", {"sample_id": obvious["id"], "conf": args.conf}, {}
        )
        elapsed = time.perf_counter() - started
        report.add(status == 200, f"detect on '{obvious['id']}' returns 200", str(status))
        if status == 200:
            check_detection_shape(report, obvious["id"], payload)
            found = len(payload.get("detections", []))
            minimum = obvious.get("expected_min_detections", 1)
            report.add(
                found >= minimum,
                f"at least {minimum} candidate(s)",
                f"{found} at conf>={args.conf}, {elapsed:.1f}s, "
                f"{payload.get('meta', {}).get('tiles')} tiles",
            )
            report.add(
                bool(payload.get("disclaimer")), "disclaimer string present and non-empty"
            )
    else:
        report.add(False, "obvious_person fixture available")

    print("\n[5] Detection — true negative")
    negative = (by_scenario.get("true_negative") or [None])[0]
    if negative:
        started = time.perf_counter()
        status, payload = post_multipart(
            f"{base}/api/detect", {"sample_id": negative["id"], "conf": args.conf}, {}
        )
        elapsed = time.perf_counter() - started
        report.add(status == 200, f"detect on '{negative['id']}' returns 200", str(status))
        if status == 200:
            check_detection_shape(report, negative["id"], payload)
            found = len(payload.get("detections", []))
            top = max((d["confidence"] for d in payload.get("detections", [])), default=0.0)
            # A true negative may still surface low-confidence clutter; that is honest
            # behaviour. It fails only if it confidently hallucinates a person.
            report.add(
                top < 0.60,
                "no high-confidence candidate on empty terrain",
                f"{found} candidate(s), top={top:.2f}, {elapsed:.1f}s",
            )
    else:
        report.add(False, "true_negative fixture available")

    print("\n[6] Detection — upload path")
    upload_source = FIXTURE_IMAGES / "lone_surfer_shorebreak.jpg"
    if upload_source.is_file():
        status, payload = post_multipart(
            f"{base}/api/detect", {"conf": args.conf}, {"image": upload_source}
        )
        report.add(status == 200, "detect via multipart upload returns 200", str(status))
        if status == 200:
            report.add(
                payload.get("meta", {}).get("source") == "upload",
                "meta.source is 'upload'",
                str(payload.get("meta", {}).get("source")),
            )
            report.add(
                payload.get("meta", {}).get("sample_id") is None,
                "meta.sample_id is null for uploads",
            )
        status, body = post_multipart(
            f"{base}/api/detect",
            {"sample_id": samples[0]["id"] if samples else "x"},
            {"image": upload_source},
        )
        report.add(status == 400, "sending both image and sample_id returns 400", str(status))
        report.add(
            body.get("error", {}).get("code") == "AMBIGUOUS_INPUT",
            "error code is AMBIGUOUS_INPUT",
            str(body.get("error", {}).get("code")),
        )
    else:
        report.add(False, f"upload fixture present ({upload_source.name})")

    total = len(report.rows)
    failures = report.failures
    print(f"\n{'=' * 60}")
    print(f"{total - failures}/{total} checks passed")
    if failures:
        print(f"\n{failures} FAILED:")
        for status, name, detail in report.rows:
            if status == FAIL:
                print(f"  - {name}" + (f" ({detail})" if detail else ""))
    print(f"{'=' * 60}\n")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
