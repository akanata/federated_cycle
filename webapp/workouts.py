"""Transform a parsed FIT activity into an OpenHost health-data Workout (JSON).

Hand-rolled to match the field names of the (in-design) spec at
github.com/imbue-openhost/health-data-service-spec without depending on it. The
output JSON mirrors the ``attrs`` types: a ``CyclingWorkout`` (a kind of
``DistanceWorkout``) with nested ``ScalarMetric`` / ``TimeSeries`` objects.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fit_route_map import Activity, to_gpx

# FIT sport -> spec WorkoutType string.
SPORT_TO_WORKOUT_TYPE = {
    "cycling": "cycling",
    "running": "running",
    "walking": "walking",
    "hiking": "hiking",
    "swimming": "swimming",
}

# Metric catalog advertised on GET /v1/metrics. Tuple = (id, display, kind, unit).
METRIC_CATALOG = [
    ("duration", "Duration", "scalar", "min"),
    ("calories", "Calories", "scalar", "kcal"),
    ("distance", "Distance", "scalar", "m"),
    ("average_speed", "Avg Speed", "scalar", "m/s"),
    ("max_speed", "Max Speed", "scalar", "m/s"),
    ("average_heart_rate", "Avg Heart Rate", "scalar", "bpm"),
    ("max_heart_rate", "Max Heart Rate", "scalar", "bpm"),
    ("heart_rate", "Heart Rate", "time_series", "bpm"),
    ("temperature", "Temperature", "scalar", "°C"),
    ("elevation_gain", "Elevation Gain", "scalar", "m"),
    ("elevation_loss", "Elevation Loss", "scalar", "m"),
    ("power", "Power", "time_series", "W"),
    ("cadence", "Cadence", "time_series", "rpm"),
]


def metric_catalog() -> list[dict]:
    return [
        {"metric_id": mid, "display_name": name, "kind": kind, "unit": unit}
        for (mid, name, kind, unit) in METRIC_CATALOG
    ]


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)  # FIT timestamps are UTC.
        return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return str(value)


def _scalar(metric_id, display_name, unit, value, source) -> Optional[dict]:
    if value is None:
        return None
    return {
        "metric_id": metric_id,
        "display_name": display_name,
        "unit": unit,
        "value": float(value),
        "source": source,
    }


def _series(metric_id, display_name, unit, samples, source) -> Optional[dict]:
    if not samples:
        return None
    return {
        "metric_id": metric_id,
        "display_name": display_name,
        "unit": unit,
        "samples": [
            {"timestamp": _iso(s.timestamp), "value": float(s.value)} for s in samples
        ],
        "source": source,
    }


def _duration_seconds(activity: Activity) -> float:
    s = activity.summary
    if s.total_timer_time is not None:
        return float(s.total_timer_time)
    if s.total_elapsed_time is not None:
        return float(s.total_elapsed_time)
    if isinstance(s.start_time, datetime) and isinstance(s.end_time, datetime):
        return max(0.0, (s.end_time - s.start_time).total_seconds())
    return 0.0


def build_workout(activity: Activity, *, id: str, source: str, detail: bool = True) -> dict:
    """Build the Workout JSON for ``activity``. ``id`` identifies the workout.

    With ``detail=False`` the result is a *summary*: scalar metrics only, with no
    per-sample time series (heart rate/power/cadence) or GPS route — this is what
    the ``/v1/workouts`` list endpoint returns per the spec. ``detail=True`` (the
    single-workout endpoint) adds the series and the GPX route.
    """

    s = activity.summary
    workout_type = SPORT_TO_WORKOUT_TYPE.get(s.sport or "", "other")

    # Required base fields (Container + Workout). calories defaults to 0 when the
    # device didn't record it, since the spec marks it non-optional.
    workout: dict = {
        "id": id,
        "start": _iso(s.start_time),
        "end": _iso(s.end_time),
        "workout_type": workout_type,
        "duration": _scalar("duration", "Duration", "min", _duration_seconds(activity) / 60.0, source),
        "calories": _scalar("calories", "Calories", "kcal", s.total_calories or 0.0, source),
        "source": source,
    }

    # Optional scalar metrics — included only when the FIT actually carried them.
    scalars = {
        "average_heart_rate": _scalar("average_heart_rate", "Avg Heart Rate", "bpm", s.avg_heart_rate, source),
        "max_heart_rate": _scalar("max_heart_rate", "Max Heart Rate", "bpm", s.max_heart_rate, source),
        "lowest_heart_rate": _scalar("lowest_heart_rate", "Lowest Heart Rate", "bpm", s.min_heart_rate, source),
        "temperature": _scalar("temperature", "Temperature", "°C", s.avg_temperature, source),
        # DistanceWorkout fields.
        "distance": _scalar("distance", "Distance", "m", s.total_distance, source),
        "average_speed": _scalar("speed", "Speed", "m/s", s.avg_speed, source),
        "max_speed": _scalar("speed", "Speed", "m/s", s.max_speed, source),
        "elevation_gain": _scalar("distance", "Distance", "m", s.total_ascent, source),
        "elevation_loss": _scalar("distance", "Distance", "m", s.total_descent, source),
        # CyclingWorkout scalar fields.
        "average_power": _scalar("average_power", "Avg Power", "W", s.avg_power, source),
        "max_power": _scalar("max_power", "Max Power", "W", s.max_power, source),
        "average_cadence": _scalar("average_cadence", "Avg Cadence", "rpm", s.avg_cadence, source),
        "max_cadence": _scalar("max_cadence", "Max Cadence", "rpm", s.max_cadence, source),
    }
    workout.update({k: v for k, v in scalars.items() if v is not None})

    if detail:
        # Per-sample time series and the GPS route — full detail only.
        series = {
            "heart_rate": _series("heart_rate", "Heart Rate", "bpm", activity.heart_rate, source),
            "power": _series("power", "Power", "W", activity.power, source),
            "cadence": _series("cadence", "Cadence", "rpm", activity.cadence, source),
        }
        workout.update({k: v for k, v in series.items() if v is not None})
        if activity.track:
            workout["route_gpx"] = to_gpx(activity.track, name=f"workout-{id}")

    return workout
