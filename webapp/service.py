"""OpenHost health-data service provider endpoints.

Declared in openhost.toml under ``[[services.v2.provides]]`` with
``endpoint = "/api/"``; the router proxies authenticated consumer calls here.
Workouts are derived on demand from the owner's stored FIT files — each FitFile
is one Workout, keyed by its database id.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from flask import Blueprint, current_app, jsonify, request

from fit_route_map import parse_activity

from . import storage
from .extensions import db
from .models import FitFile
from .workouts import SPORT_TO_WORKOUT_TYPE, build_workout, metric_catalog

bp = Blueprint("service", __name__, url_prefix="/api")


def _source() -> str:
    return current_app.config["WORKOUT_SOURCE"]


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _workout_for(fit: FitFile, *, detail: bool) -> dict:
    activity = parse_activity(storage.fit_path(fit.stored_name))
    return build_workout(activity, id=str(fit.id), source=_source(), detail=detail)


@bp.get("/v1/metrics")
def list_metrics():
    return jsonify({"metrics": metric_catalog()})


@bp.get("/v1/workouts")
def list_workouts():
    workout_type = request.args.get("workout_type")
    start = _parse_dt(request.args.get("start"))
    end = _parse_dt(request.args.get("end"))
    limit = request.args.get("limit", type=int)

    query = FitFile.query
    if workout_type is not None:
        # Map the requested spec type back to the FIT sports that produce it.
        sports = [s for s, wt in SPORT_TO_WORKOUT_TYPE.items() if wt == workout_type]
        query = query.filter(FitFile.sport.in_(sports)) if sports else query.filter(False)
    if start is not None:
        query = query.filter(FitFile.started_at >= _naive_utc(start))
    if end is not None:
        query = query.filter(FitFile.started_at <= _naive_utc(end))

    files = query.order_by(FitFile.started_at.desc()).all()
    # The list endpoint returns summaries (scalars only); detail is per-id.
    workouts = [_workout_for(f, detail=False) for f in files]
    if limit is not None:
        workouts = workouts[: max(0, limit)]
    return jsonify({"data": workouts})


@bp.get("/v1/workouts/<int:workout_id>")
def get_workout(workout_id: int):
    fit = db.session.get(FitFile, workout_id)
    if fit is None:
        return jsonify({"error": "not_found"}), 404
    return jsonify(_workout_for(fit, detail=True))


# We hold workout data only. Return correctly-shaped empties so consumers that
# also query other health metrics get valid (empty) responses, not errors.
@bp.get("/v1/time-series")
def time_series():
    metric = request.args.get("metric", "")
    return jsonify(
        {"metric_id": metric, "display_name": metric, "unit": None,
         "samples": [], "source": _source()}
    )


@bp.get("/v1/sleep-sessions")
def sleep_sessions():
    return jsonify({"data": []})


def _naive_utc(dt: datetime) -> datetime:
    """started_at is stored naive-UTC; normalise query bounds to naive UTC to match."""

    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt
