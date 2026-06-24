import io
from pathlib import Path

import pytest
from PIL import Image

from webapp import create_app
from webapp.config import TestConfig
from webapp.extensions import db
from webapp.models import FitFile

SAMPLE_FIT = Path(__file__).resolve().parent.parent / "examples" / "cycle.fit"


@pytest.fixture
def app(tmp_path):
    class Cfg(TestConfig):
        UPLOAD_DIR = tmp_path / "uploads"
        TILE_CACHE_DIR = tmp_path / "tiles"

    app = create_app(Cfg)
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def upload_sample(client, filename="cycle.fit"):
    data = {"fit_file": (io.BytesIO(SAMPLE_FIT.read_bytes()), filename)}
    return client.post(
        "/upload", data=data, content_type="multipart/form-data", follow_redirects=True
    )


def test_dashboard_loads_without_login(client):
    # No auth: the dashboard is reachable directly.
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Upload a ride" in resp.data


def test_upload_creates_record_and_caches_metadata(client, app):
    resp = upload_sample(client)
    assert resp.status_code == 200
    assert b"uploaded cycle.fit" in resp.data.lower()

    with app.app_context():
        files = FitFile.query.all()
        assert len(files) == 1
        fit = files[0]
        assert fit.original_filename == "cycle.fit"
        assert fit.point_count > 0
        assert fit.sport == "cycling"
        assert fit.started_at is not None
        stored = Path(app.config["UPLOAD_DIR"]) / fit.stored_name
        assert stored.exists()


def test_non_fit_upload_rejected(client, app):
    data = {"fit_file": (io.BytesIO(b"not a fit file"), "notes.txt")}
    resp = client.post(
        "/upload", data=data, content_type="multipart/form-data", follow_redirects=True
    )
    assert b"only .fit files" in resp.data.lower()
    with app.app_context():
        assert FitFile.query.count() == 0


def test_render_endpoint_returns_png(client, app, monkeypatch):
    import webapp.storage as storage

    def fake_fit_to_image(source, output_path=None, *, options=None, tile_provider=None):
        img = Image.new("RGBA", (64, 48), (10, 20, 30, 255))
        if output_path is not None:
            img.save(output_path)
        return img

    monkeypatch.setattr(storage, "fit_to_image", fake_fit_to_image)

    upload_sample(client)
    with app.app_context():
        file_id = FitFile.query.first().id

    resp = client.get(f"/files/{file_id}/image.png")
    assert resp.status_code == 200
    assert resp.mimetype == "image/png"
    assert Image.open(io.BytesIO(resp.data)).size == (64, 48)


def test_delete_removes_record_and_files(client, app):
    upload_sample(client)
    with app.app_context():
        fit = FitFile.query.first()
        file_id = fit.id
        stored = Path(app.config["UPLOAD_DIR"]) / fit.stored_name
    assert stored.exists()

    client.post(f"/files/{file_id}/delete", follow_redirects=True)
    with app.app_context():
        assert FitFile.query.count() == 0
    assert not stored.exists()


def test_missing_file_404(client):
    assert client.get("/files/999/view").status_code == 404
    assert client.get("/files/999/image.png").status_code == 404
