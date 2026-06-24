"""Lightweight workout analysis used for sorting (heart-rate intensity)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Sequence

from fit_route_map import Sample

# Zone boundaries as a fraction of max HR (Z1 <60%, Z2, Z3, Z4, Z5 >=90%).
_ZONE_EDGES = (0.6, 0.7, 0.8, 0.9)


def hr_zone(hr: Optional[float], max_hr: float) -> int:
    """Return the heart-rate zone (1–5) for ``hr`` given ``max_hr``; 0 if unknown."""

    if hr is None or max_hr <= 0:
        return 0
    frac = hr / max_hr
    zone = 1
    for edge in _ZONE_EDGES:
        if frac >= edge:
            zone += 1
    return zone


def _delta_seconds(a, b) -> Optional[float]:
    if isinstance(a, datetime) and isinstance(b, datetime):
        return b.timestamp() - a.timestamp()
    return None


def hr_zone_intensity(
    samples: Sequence[Sample], max_hr: float, *, max_gap: float = 10.0
) -> float:
    """Time-weighted heart-rate-zone effort score.

    Each interval between consecutive HR samples contributes ``seconds × zone``,
    so time spent in higher zones counts for more. Gaps longer than ``max_gap``
    (pauses, dropouts) or non-monotonic timestamps fall back to a 1-second step.
    Returns 0.0 for rides with no usable heart-rate data.
    """

    score = 0.0
    prev: Optional[Sample] = None
    for s in samples:
        if prev is not None:
            dt = _delta_seconds(prev.timestamp, s.timestamp)
            if dt is None or dt <= 0 or dt > max_gap:
                dt = 1.0
            score += dt * hr_zone(prev.value, max_hr)
        prev = s
    return score
