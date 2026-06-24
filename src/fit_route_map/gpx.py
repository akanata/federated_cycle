"""Serialize a GPS track to a GPX 1.1 document."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Optional, Sequence

from .parser import TrackPoint

GPX_NAMESPACE = "http://www.topografix.com/GPX/1/1"


def _iso_utc(value) -> Optional[str]:
    """Format a datetime as an ISO 8601 UTC string with a trailing ``Z``."""

    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)  # FIT timestamps are UTC.
        value = value.astimezone(timezone.utc)
        return value.strftime("%Y-%m-%dT%H:%M:%SZ")
    return str(value)


def to_gpx(
    points: Sequence[TrackPoint],
    *,
    name: Optional[str] = None,
    creator: str = "fit-route-map",
) -> str:
    """Render ``points`` as a GPX 1.1 document string (single track, single segment)."""

    gpx = ET.Element(
        "gpx", {"version": "1.1", "creator": creator, "xmlns": GPX_NAMESPACE}
    )
    trk = ET.SubElement(gpx, "trk")
    if name:
        ET.SubElement(trk, "name").text = name
    seg = ET.SubElement(trk, "trkseg")

    for p in points:
        pt = ET.SubElement(
            seg, "trkpt", {"lat": f"{p.lat:.7f}", "lon": f"{p.lon:.7f}"}
        )
        if p.altitude is not None:
            ET.SubElement(pt, "ele").text = f"{float(p.altitude):.2f}"
        ts = _iso_utc(p.timestamp)
        if ts is not None:
            ET.SubElement(pt, "time").text = ts

    body = ET.tostring(gpx, encoding="unicode")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + body
