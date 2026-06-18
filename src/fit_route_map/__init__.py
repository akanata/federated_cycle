"""Convert FIT activity files into an image of the route overlaid on a map."""

from __future__ import annotations

from .api import fit_to_image
from .geo import BoundingBox, choose_zoom, lonlat_to_world
from .parser import TrackPoint, parse_fit
from .renderer import RouteMapOptions, render_route
from .tiles import TileProvider

__version__ = "0.1.0"

__all__ = [
    "fit_to_image",
    "parse_fit",
    "TrackPoint",
    "render_route",
    "RouteMapOptions",
    "TileProvider",
    "BoundingBox",
    "choose_zoom",
    "lonlat_to_world",
    "__version__",
]
