"""Parse FIT activity files into a list of GPS track points."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional, Union

from fitparse import FitFile

# FIT stores positions as 32-bit "semicircles". 2**31 semicircles == 180 degrees.
SEMICIRCLE_TO_DEGREES = 180.0 / (2 ** 31)

PathLike = Union[str, Path]


@dataclass
class TrackPoint:
    """A single recorded GPS sample."""

    lat: float
    lon: float
    timestamp: Any = None
    altitude: Optional[float] = None


def _to_degrees(semicircles: Optional[float]) -> Optional[float]:
    if semicircles is None:
        return None
    return semicircles * SEMICIRCLE_TO_DEGREES


def parse_fit(path: PathLike) -> List[TrackPoint]:
    """Read a FIT file and return its GPS track as a list of :class:`TrackPoint`.

    Records without a latitude/longitude (e.g. samples taken before GPS lock) are
    skipped. Latitude and longitude are converted from FIT semicircles to degrees.
    """

    fit = FitFile(str(path))
    points: List[TrackPoint] = []
    for record in fit.get_messages("record"):
        values = record.get_values()
        lat = values.get("position_lat")
        lon = values.get("position_long")
        if lat is None or lon is None:
            continue
        points.append(
            TrackPoint(
                lat=_to_degrees(lat),
                lon=_to_degrees(lon),
                timestamp=values.get("timestamp"),
                altitude=values.get("enhanced_altitude", values.get("altitude")),
            )
        )
    return points
