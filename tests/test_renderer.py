import pytest
from PIL import Image

from fit_route_map.parser import TrackPoint
from fit_route_map.renderer import RouteMapOptions, render_route


class FakeTileProvider:
    """Returns a solid-grey tile without any network access."""

    def __init__(self, color=(200, 200, 200, 255)):
        self.color = color
        self.requested = []

    def get_tile(self, x, y, z):
        self.requested.append((x, y, z))
        return Image.new("RGBA", (256, 256), self.color)


def _sample_points():
    # A short diagonal track across central London.
    return [
        TrackPoint(lat=51.500, lon=-0.130),
        TrackPoint(lat=51.505, lon=-0.120),
        TrackPoint(lat=51.510, lon=-0.110),
        TrackPoint(lat=51.512, lon=-0.100),
    ]


def test_render_produces_correct_size():
    opts = RouteMapOptions(width=640, height=480, line_color=(255, 0, 0, 255))
    img = render_route(_sample_points(), FakeTileProvider(), opts)
    assert img.size == (640, 480)
    assert img.mode == "RGBA"


def test_route_pixels_are_drawn():
    line = (255, 0, 0, 255)
    opts = RouteMapOptions(
        width=640, height=480, line_color=line, line_width=6, show_markers=False
    )
    img = render_route(_sample_points(), FakeTileProvider(color=(180, 180, 180, 255)), opts)

    colors = {c for _, c in img.getcolors(maxcolors=100000)}
    # The exact line colour should appear somewhere in the image.
    assert line in colors


def test_markers_drawn_when_enabled():
    start = (0, 255, 0, 255)
    end = (0, 0, 255, 255)
    opts = RouteMapOptions(
        width=640,
        height=480,
        show_markers=True,
        start_color=start,
        end_color=end,
        line_width=4,
    )
    img = render_route(_sample_points(), FakeTileProvider(), opts)
    colors = {c for _, c in img.getcolors(maxcolors=100000)}
    assert start in colors
    assert end in colors


def test_tile_fetch_failure_is_tolerated():
    class BrokenProvider:
        def get_tile(self, x, y, z):
            raise RuntimeError("network down")

    opts = RouteMapOptions(width=320, height=240, background=(238, 238, 238, 255))
    # Should still render (route over the background) without raising.
    img = render_route(_sample_points(), BrokenProvider(), opts)
    assert img.size == (320, 240)


def test_empty_points_raises():
    with pytest.raises(ValueError):
        render_route([], FakeTileProvider())
