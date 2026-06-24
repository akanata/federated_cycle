import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from fit_route_map import TrackPoint, to_gpx

NS = {"g": "http://www.topografix.com/GPX/1/1"}


def _points():
    return [
        TrackPoint(lat=51.5, lon=-0.12, timestamp=datetime(2026, 6, 7, 23, 6, 37), altitude=37.2),
        TrackPoint(lat=51.51, lon=-0.11, timestamp=datetime(2026, 6, 7, 23, 7, 0), altitude=40.0),
    ]


def test_gpx_is_well_formed_and_structured():
    gpx = to_gpx(_points(), name="ride")
    assert gpx.startswith('<?xml version="1.0" encoding="UTF-8"?>')

    root = ET.fromstring(gpx.split("\n", 1)[1])
    assert root.attrib["version"] == "1.1"

    pts = root.findall(".//g:trkpt", NS)
    assert len(pts) == 2
    assert pts[0].attrib["lat"] == "51.5000000"
    assert pts[0].attrib["lon"] == "-0.1200000"
    assert pts[0].find("g:ele", NS).text == "37.20"
    assert pts[0].find("g:time", NS).text == "2026-06-07T23:06:37Z"
    assert root.find(".//g:trk/g:name", NS).text == "ride"


def test_timezone_aware_timestamp_normalised_to_utc():
    pt = TrackPoint(
        lat=0.0, lon=0.0,
        timestamp=datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
        altitude=None,
    )
    gpx = to_gpx([pt])
    root = ET.fromstring(gpx.split("\n", 1)[1])
    trkpt = root.find(".//g:trkpt", NS)
    assert trkpt.find("g:time", NS).text == "2026-01-01T12:00:00Z"
    assert trkpt.find("g:ele", NS) is None  # no altitude -> no <ele>
