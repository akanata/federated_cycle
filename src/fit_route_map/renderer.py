"""Render a GPS track onto a stitched map background."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw

from .geo import TILE_SIZE, BoundingBox, choose_zoom, lonlat_to_world
from .parser import TrackPoint
from .tiles import TileProvider

RGBA = Tuple[int, int, int, int]


@dataclass
class RouteMapOptions:
    """Styling and sizing options for :func:`render_route`."""

    width: int = 1200
    height: int = 800
    padding: int = 60
    line_color: RGBA = (224, 26, 79, 255)
    line_width: int = 5
    show_markers: bool = True
    start_color: RGBA = (40, 167, 69, 255)
    end_color: RGBA = (40, 40, 40, 255)
    marker_radius: int = 7
    background: RGBA = (238, 238, 238, 255)
    min_zoom: int = 0
    max_zoom: int = 19


def render_route(
    points: Sequence[TrackPoint],
    tile_provider: Optional[TileProvider] = None,
    options: Optional[RouteMapOptions] = None,
) -> Image.Image:
    """Render ``points`` as a route drawn over map tiles.

    Returns an RGBA :class:`PIL.Image.Image` of ``options.width`` x
    ``options.height``. Tiles that fail to download are skipped, leaving the
    background colour showing through, so the route is still produced even if the
    map is partially unavailable.
    """

    if not points:
        raise ValueError("Cannot render a route with no points")

    options = options or RouteMapOptions()
    tile_provider = tile_provider or TileProvider()

    latlon = [(p.lat, p.lon) for p in points]
    bbox = BoundingBox.from_points(latlon)
    zoom = choose_zoom(
        bbox, options.width, options.height, options.padding,
        options.min_zoom, options.max_zoom,
    )

    world = [lonlat_to_world(lon, lat, zoom) for lat, lon in latlon]
    xs = [x for x, _ in world]
    ys = [y for _, y in world]

    # Top-left of the canvas in world pixels, centring the route's bbox.
    origin_x = (min(xs) + max(xs)) / 2 - options.width / 2
    origin_y = (min(ys) + max(ys)) / 2 - options.height / 2

    canvas = _render_base_map(tile_provider, origin_x, origin_y, zoom, options)

    draw = ImageDraw.Draw(canvas, "RGBA")
    pixels = [(x - origin_x, y - origin_y) for x, y in world]
    if len(pixels) >= 2:
        draw.line(pixels, fill=options.line_color, width=options.line_width, joint="curve")
    if options.show_markers:
        _draw_marker(draw, pixels[0], options.start_color, options.marker_radius)
        _draw_marker(draw, pixels[-1], options.end_color, options.marker_radius)

    return canvas


def _render_base_map(
    provider: TileProvider,
    origin_x: float,
    origin_y: float,
    zoom: int,
    options: RouteMapOptions,
) -> Image.Image:
    canvas = Image.new("RGBA", (options.width, options.height), options.background)
    n_tiles = 2 ** zoom

    min_tx = math.floor(origin_x / TILE_SIZE)
    max_tx = math.floor((origin_x + options.width) / TILE_SIZE)
    min_ty = math.floor(origin_y / TILE_SIZE)
    max_ty = math.floor((origin_y + options.height) / TILE_SIZE)

    for tx in range(min_tx, max_tx + 1):
        for ty in range(min_ty, max_ty + 1):
            if ty < 0 or ty >= n_tiles:
                continue  # No tiles above the north pole / below the south pole.
            wrapped_tx = tx % n_tiles  # Allow the map to wrap around the antimeridian.
            try:
                tile = provider.get_tile(wrapped_tx, ty, zoom)
            except Exception:
                continue  # Missing tile -> leave the background showing.
            px = round(tx * TILE_SIZE - origin_x)
            py = round(ty * TILE_SIZE - origin_y)
            canvas.alpha_composite(tile, (px, py))
    return canvas


def _draw_marker(
    draw: ImageDraw.ImageDraw, xy: Tuple[float, float], color: RGBA, radius: int
) -> None:
    x, y = xy
    draw.ellipse(
        [x - radius, y - radius, x + radius, y + radius],
        fill=color,
        outline=(255, 255, 255, 255),
        width=2,
    )
