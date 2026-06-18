import math

import pytest

from fit_route_map.geo import (
    TILE_SIZE,
    BoundingBox,
    choose_zoom,
    lonlat_to_world,
)


def test_origin_maps_to_world_centre():
    # (lon=0, lat=0) is the centre of the world map.
    for zoom in range(0, 5):
        x, y = lonlat_to_world(0.0, 0.0, zoom)
        half = TILE_SIZE * (2 ** zoom) / 2
        assert x == pytest.approx(half)
        assert y == pytest.approx(half)


def test_corners_of_the_world():
    # At zoom 0 the whole world is a single 256px tile.
    x, y = lonlat_to_world(-180.0, 85.0511, 0)
    assert x == pytest.approx(0.0, abs=1e-6)
    assert y == pytest.approx(0.0, abs=1e-3)

    x, _ = lonlat_to_world(180.0, 0.0, 0)
    assert x == pytest.approx(TILE_SIZE)


def test_x_increases_eastward_y_increases_southward():
    west_x, _ = lonlat_to_world(-10.0, 50.0, 8)
    east_x, _ = lonlat_to_world(10.0, 50.0, 8)
    assert east_x > west_x

    _, north_y = lonlat_to_world(0.0, 60.0, 8)
    _, south_y = lonlat_to_world(0.0, 40.0, 8)
    assert south_y > north_y


def test_bounding_box_from_points():
    pts = [(50.0, -1.0), (51.0, 1.0), (49.5, 0.5)]
    bbox = BoundingBox.from_points(pts)
    assert bbox.min_lat == 49.5
    assert bbox.max_lat == 51.0
    assert bbox.min_lon == -1.0
    assert bbox.max_lon == 1.0


def test_bounding_box_requires_points():
    with pytest.raises(ValueError):
        BoundingBox.from_points([])


def test_choose_zoom_fits_within_canvas():
    bbox = BoundingBox(min_lat=51.50, min_lon=-0.13, max_lat=51.52, max_lon=-0.10)
    zoom = choose_zoom(bbox, width=800, height=600, padding=40)

    x0, y0 = lonlat_to_world(bbox.min_lon, bbox.max_lat, zoom)
    x1, y1 = lonlat_to_world(bbox.max_lon, bbox.min_lat, zoom)
    assert abs(x1 - x0) <= 800 - 2 * 40
    assert abs(y1 - y0) <= 600 - 2 * 40

    # One zoom deeper would overflow the usable area.
    x0d, y0d = lonlat_to_world(bbox.min_lon, bbox.max_lat, zoom + 1)
    x1d, y1d = lonlat_to_world(bbox.max_lon, bbox.min_lat, zoom + 1)
    overflows = (abs(x1d - x0d) > 800 - 2 * 40) or (abs(y1d - y0d) > 600 - 2 * 40)
    assert overflows


def test_choose_zoom_clamps_to_min_for_huge_bbox():
    world = BoundingBox(min_lat=-80.0, min_lon=-179.0, max_lat=80.0, max_lon=179.0)
    assert choose_zoom(world, width=256, height=256, padding=0, min_zoom=0) == 0
