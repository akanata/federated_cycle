import io
from pathlib import Path

import pytest

from fit_route_map import parse_activity
from webapp import create_app
from webapp.config import TestConfig
from webapp.extensions import db
from webapp.models import FitFile
from webapp.workouts import build_workout

SAMPLE_FIT = Path(__file__).resolve().parent.parent / "examples" / "cycle.fit"


# ---------------------------------------------------------------------------
# Pure transform (no Flask)
# ---------------------------------------------------------------------------

def test_build_workout_shape_for_cycling_sample():
    activity = parse_activity(SAMPLE_FIT)
    w = build_workout(activity, id="42", source="fit-route-map")

    # Container + required Workout fields.
    assert w["id"] == "42"
    assert w["workout_type"] == "cycling"
    assert w["source"] == "fit-route-map"
    assert w["start"].endswith("Z") and w["end"].endswith("Z")

    # duration/calories are required ScalarMetrics with the documented shape.
    for key in ("duration", "calories"):
        m = w[key]
        assert set(m) == {"metric_id", "display_name", "unit", "value", "source"}
        assert isinstance(m["value"], float)
    assert w["duration"]["unit"] == "min"
    assert w["duration"]["value"] > 0

    # DistanceWorkout fields present for this ride.
    assert w["distance"]["unit"] == "m" and w["distance"]["value"] > 0
    assert "route_gpx" in w and "<trkpt" in w["route_gpx"]

    # Heart-rate series present and well-shaped.
    hr = w["heart_rate"]
    assert hr["metric_id"] == "heart_rate" and hr["unit"] == "bpm"
    assert hr["samples"] and set(hr["samples"][0]) == {"timestamp", "value"}

    # This sample has no power/cadence sensors -> those keys are omitted.
    assert "power" not in w
    assert "cadence" not in w


def test_missing_calories_defaults_to_zero(monkeypatch):
    activity = parse_activity(SAMPLE_FIT)
    activity.summary.total_calories = None
    w = build_workout(activity, id="1", source="src")
    assert w["calories"]["value"] == 0.0


# ---------------------------------------------------------------------------
# Provider API endpoints
# ---------------------------------------------------------------------------

@pytest.fixture
def client(tmp_path):
    class Cfg(TestConfig):
        UPLOAD_DIR = tmp_path / "uploads"
        TILE_CACHE_DIR = tmp_path / "tiles"

    app = create_app(Cfg)
    c = app.test_client()
    c._app = app
    yield c
    with app.app_context():
        db.session.remove()
        db.drop_all()


def _upload(client):
    data = {"fit_file": (io.BytesIO(SAMPLE_FIT.read_bytes()), "cycle.fit")}
    client.post("/upload", data=data, content_type="multipart/form-data", follow_redirects=True)
    with client._app.app_context():
        return FitFile.query.first().id


def test_metrics_endpoint(client):
    resp = client.get("/api/v1/metrics")
    assert resp.status_code == 200
    catalog = resp.get_json()
    ids = {m["metric_id"] for m in catalog}
    assert {"duration", "distance", "heart_rate"} <= ids
    assert all({"metric_id", "display_name", "kind", "unit"} <= set(m) for m in catalog)


def test_list_and_get_workout(client):
    file_id = _upload(client)

    listed = client.get("/api/v1/workouts").get_json()
    assert len(listed) == 1
    assert listed[0]["id"] == str(file_id)
    assert listed[0]["workout_type"] == "cycling"

    single = client.get(f"/api/v1/workouts/{file_id}").get_json()
    assert single["id"] == str(file_id)
    assert "route_gpx" in single


def test_workout_type_filter(client):
    _upload(client)
    assert len(client.get("/api/v1/workouts?workout_type=cycling").get_json()) == 1
    assert client.get("/api/v1/workouts?workout_type=running").get_json() == []


def test_limit_filter(client):
    _upload(client)
    assert client.get("/api/v1/workouts?limit=0").get_json() == []


def test_unknown_workout_404(client):
    resp = client.get("/api/v1/workouts/9999")
    assert resp.status_code == 404


def test_empty_timeseries_and_sleep(client):
    assert client.get("/api/v1/time-series").get_json() == []
    assert client.get("/api/v1/sleep-sessions").get_json() == []
