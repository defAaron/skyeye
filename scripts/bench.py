"""Measure detection behaviour across the whole demo corpus.

Produces the numbers to quote out loud instead of guessing:

    backend/venv/bin/python scripts/bench.py
    backend/venv/bin/python scripts/bench.py --conf 0.15

For scenario `true_negative` fixtures, every candidate is by definition a false
positive, so the "hits" column is the false-positive count.
"""

from __future__ import annotations

import argparse
import time

from smoke import get_json, post_multipart


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:5001")
    parser.add_argument("--conf", default="0.25")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    status, payload = get_json(f"{base}/api/samples")
    if status != 200:
        print("Backend unreachable. Start it: cd backend && venv/bin/python app.py")
        return 1
    samples = payload.get("samples", [])
    if not samples:
        print("No fixtures. Run: cd backend && venv/bin/python fixtures/fetch_fixtures.py")
        return 1

    print(f"\nconf threshold = {args.conf}\n")
    header = f"{'fixture':24s} {'scenario':15s} {'size':>11s} {'tiles':>6s} {'s':>6s} {'cand':>5s} {'min':>4s} {'top':>5s}"
    print(header)
    print("-" * len(header))

    scenario_totals: dict[str, list[int]] = {}
    misses: list[str] = []
    slowest = 0.0

    for sample in samples:
        started = time.perf_counter()
        status, result = post_multipart(
            f"{base}/api/detect", {"sample_id": sample["id"], "conf": args.conf}, {}
        )
        elapsed = time.perf_counter() - started
        slowest = max(slowest, elapsed)

        if status != 200:
            print(f"{sample['id']:24s} ERROR {status} {result.get('error', {}).get('code', '')}")
            misses.append(sample["id"])
            continue

        detections = result.get("detections", [])
        top = max((d["confidence"] for d in detections), default=0.0)
        minimum = sample.get("expected_min_detections", 0)
        scenario = sample.get("scenario", "?")
        met = len(detections) >= minimum if scenario != "true_negative" else top < 0.60
        flag = "" if met else "   <-- MISS"
        if not met:
            misses.append(sample["id"])

        counts = scenario_totals.setdefault(scenario, [0, 0])
        counts[0] += 1
        counts[1] += 1 if met else 0

        print(
            f"{sample['id']:24s} {scenario:15s} "
            f"{result['image_width']}x{result['image_height']:<5} "
            f"{result.get('meta', {}).get('tiles', 0):6d} {elapsed:6.1f} "
            f"{len(detections):5d} {minimum:4d} {top:5.2f}{flag}"
        )

    print()
    for scenario, (total, met) in sorted(scenario_totals.items()):
        label = "no false positive >=0.60" if scenario == "true_negative" else "met expected_min"
        print(f"  {scenario:15s} {met}/{total} {label}")
    print(f"\n  slowest fixture: {slowest:.1f}s (demo target for first lead: <30s)")
    if misses:
        print(f"  misses: {', '.join(misses)}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
