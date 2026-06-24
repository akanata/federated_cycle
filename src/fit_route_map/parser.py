"""Parse FIT activity files into GPS track points and activity summaries."""

from __future__ import annotations

from dataclasses import dataclass, field
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


@dataclass
class Sample:
    """A single timestamped sensor reading (heart rate, power, cadence)."""

    timestamp: Any
    value: float


@dataclass
class ActivitySummary:
    """Session-level totals/averages for a whole activity.

    Every field is optional because availability varies by device and sport.
    """

    sport: Optional[str] = None
    start_time: Optional[Any] = None
    end_time: Optional[Any] = None
    total_timer_time: Optional[float] = None  # seconds (moving time)
    total_elapsed_time: Optional[float] = None  # seconds (wall-clock)
    total_distance: Optional[float] = None  # metres
    total_calories: Optional[float] = None  # kcal
    total_ascent: Optional[float] = None  # metres
    total_descent: Optional[float] = None  # metres
    avg_speed: Optional[float] = None  # m/s
    max_speed: Optional[float] = None  # m/s
    avg_heart_rate: Optional[float] = None  # bpm
    max_heart_rate: Optional[float] = None  # bpm
    min_heart_rate: Optional[float] = None  # bpm
    avg_power: Optional[float] = None  # W
    max_power: Optional[float] = None  # W
    avg_cadence: Optional[float] = None  # rpm
    max_cadence: Optional[float] = None  # rpm
    avg_temperature: Optional[float] = None  # °C


@dataclass
class Activity:
    """A parsed activity: summary, GPS track, and per-sample sensor series."""

    summary: ActivitySummary
    track: List[TrackPoint] = field(default_factory=list)
    heart_rate: List[Sample] = field(default_factory=list)
    power: List[Sample] = field(default_factory=list)
    cadence: List[Sample] = field(default_factory=list)


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
    return _read_track(fit)


def _read_track(fit: FitFile) -> List[TrackPoint]:
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


def _pick(values: dict, *names: str) -> Optional[Any]:
    """Return the first present (non-None) value among ``names``."""

    for name in names:
        val = values.get(name)
        if val is not None:
            return val
    return None


def parse_activity(path: PathLike) -> Activity:
    """Read a FIT file into an :class:`Activity` (summary + track + sensor series).

    A single pass over the ``record`` messages collects the GPS track and any
    heart-rate / power / cadence samples; the ``session`` message supplies the
    summary totals. Missing fields stay ``None`` / empty.
    """

    fit = FitFile(str(path))

    track: List[TrackPoint] = []
    heart_rate: List[Sample] = []
    power: List[Sample] = []
    cadence: List[Sample] = []

    for record in fit.get_messages("record"):
        v = record.get_values()
        ts = v.get("timestamp")
        lat, lon = v.get("position_lat"), v.get("position_long")
        if lat is not None and lon is not None:
            track.append(
                TrackPoint(
                    lat=_to_degrees(lat),
                    lon=_to_degrees(lon),
                    timestamp=ts,
                    altitude=v.get("enhanced_altitude", v.get("altitude")),
                )
            )
        if v.get("heart_rate") is not None:
            heart_rate.append(Sample(ts, float(v["heart_rate"])))
        if v.get("power") is not None:
            power.append(Sample(ts, float(v["power"])))
        if v.get("cadence") is not None:
            cadence.append(Sample(ts, float(v["cadence"])))

    summary = _read_summary(fit, track)
    return Activity(
        summary=summary,
        track=track,
        heart_rate=heart_rate,
        power=power,
        cadence=cadence,
    )


def _read_summary(fit: FitFile, track: List[TrackPoint]) -> ActivitySummary:
    summary = ActivitySummary()
    session = next(iter(fit.get_messages("session")), None)
    if session is not None:
        v = session.get_values()
        summary.sport = v.get("sport")
        summary.start_time = v.get("start_time")
        summary.end_time = v.get("timestamp")
        summary.total_timer_time = v.get("total_timer_time")
        summary.total_elapsed_time = v.get("total_elapsed_time")
        summary.total_distance = v.get("total_distance")
        summary.total_calories = v.get("total_calories")
        summary.total_ascent = v.get("total_ascent")
        summary.total_descent = v.get("total_descent")
        summary.avg_speed = _pick(v, "enhanced_avg_speed", "avg_speed")
        summary.max_speed = _pick(v, "enhanced_max_speed", "max_speed")
        summary.avg_heart_rate = v.get("avg_heart_rate")
        summary.max_heart_rate = v.get("max_heart_rate")
        summary.min_heart_rate = v.get("min_heart_rate")
        summary.avg_power = v.get("avg_power")
        summary.max_power = v.get("max_power")
        summary.avg_cadence = v.get("avg_cadence")
        summary.max_cadence = v.get("max_cadence")
        summary.avg_temperature = v.get("avg_temperature")

    # Fall back to the track's own timestamps when the session lacks them.
    if summary.start_time is None and track and track[0].timestamp is not None:
        summary.start_time = track[0].timestamp
    if summary.end_time is None and track and track[-1].timestamp is not None:
        summary.end_time = track[-1].timestamp
    return summary
