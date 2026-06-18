"""Web Mercator (slippy-map) projection helpers.

All functions here are pure and free of I/O so they can be unit-tested without a
network connection. The coordinate system used throughout is the standard XYZ /
slippy-map scheme used by OpenStreetMap and most tile servers: at zoom ``z`` the
world is a square of ``2**z`` tiles per side, each :data:`TILE_SIZE` pixels.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Sequence, Tuple

TILE_SIZE = 256

LatLon = Tuple[float, float]


@dataclass(frozen=True)
class BoundingBox:
    """Geographic bounds of a set of points, in degrees."""

    min_lat: float
    min_lon: float
    max_lat: float
    max_lon: float

    @classmethod
    def from_points(cls, points: Iterable[LatLon]) -> "BoundingBox":
        points = list(points)
        if not points:
            raise ValueError("Cannot build a bounding box from zero points")
        lats = [lat for lat, _ in points]
        lons = [lon for _, lon in points]
        return cls(min(lats), min(lons), max(lats), max(lons))


def lonlat_to_world(lon: float, lat: float, zoom: int) -> Tuple[float, float]:
    """Project ``(lon, lat)`` to global pixel coordinates at ``zoom``.

    The returned ``(x, y)`` are floating-point pixel offsets from the top-left of
    the whole world map (north-west corner). ``x`` increases eastward, ``y``
    increases southward.
    """

    n = TILE_SIZE * (2 ** zoom)
    x = (lon + 180.0) / 360.0 * n
    lat_rad = math.radians(lat)
    y = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n
    return x, y


def choose_zoom(
    bbox: BoundingBox,
    width: int,
    height: int,
    padding: int = 0,
    min_zoom: int = 0,
    max_zoom: int = 19,
) -> int:
    """Pick the largest zoom whose route bbox fits ``width`` x ``height``.

    ``padding`` reserves a margin (in pixels) on every side so the route does not
    touch the image edge. If the route does not fit at any zoom, ``min_zoom`` is
    returned.
    """

    usable_w = max(1, width - 2 * padding)
    usable_h = max(1, height - 2 * padding)
    for zoom in range(max_zoom, min_zoom - 1, -1):
        # North-west corner has the smallest y, south-east the largest.
        x0, y0 = lonlat_to_world(bbox.min_lon, bbox.max_lat, zoom)
        x1, y1 = lonlat_to_world(bbox.max_lon, bbox.min_lat, zoom)
        if abs(x1 - x0) <= usable_w and abs(y1 - y0) <= usable_h:
            return zoom
    return min_zoom


def project_points(
    points: Sequence[LatLon], zoom: int
) -> list[Tuple[float, float]]:
    """Project a sequence of ``(lat, lon)`` points to world pixels at ``zoom``."""

    return [lonlat_to_world(lon, lat, zoom) for lat, lon in points]
