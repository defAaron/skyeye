"""Simplified Lost Person Behavior search-radius heuristic.

Real SAR uses Koester distance tables (subject category × terrain × percentile).
This is a demo-scale stand-in: a 50th-percentile distance treated as the radius
at 3 elapsed hours, then scaled with sqrt(time) so doubling time does not
double the ring. It is not operational search planning.
"""

from __future__ import annotations

import math

# Metres at 3 elapsed hours (a typical time-to-find midpoint in the literature).
P50_M: dict[str, int] = {
    "child": 500,
    "youth": 1000,
    "elderly": 800,
    "elderly_hiker": 1100,
    "dementia": 750,
    "hiker": 1900,
    "hunter": 1600,
    "unknown": 1200,
}

CATEGORIES: tuple[str, ...] = tuple(P50_M.keys())

MIN_RADIUS_M = 200
MAX_RADIUS_M = 8000
REFERENCE_HOURS = 3.0

LPB_NOTE = (
    "Simplified 50th-percentile Lost Person Behavior radius, scaled with "
    "elapsed time. Not a guarantee the subject is inside the ring."
)


def radius_m(category: str, elapsed_hours: float) -> int:
    p50 = P50_M[category]
    raw = p50 * math.sqrt(elapsed_hours / REFERENCE_HOURS)
    return int(round(min(MAX_RADIUS_M, max(MIN_RADIUS_M, raw))))
