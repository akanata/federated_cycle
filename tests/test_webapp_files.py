import io
from pathlib import Path

import pyotp
import pytest
from PIL import Image

from webapp import create_app
from webapp.config import TestConfig
from webapp.extensions import db
from webapp.models import FitFile, User

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


def _signup(client, app, username, password="hunter2pass"):
    """Register + complete TOTP enrollment, leaving the client logged in."""
    client.post(
        "/register",
        data={"username": username, "password": password, "confirm": password},
        follow_redirects=True,
    )
    with app.app_context():
        secret = User.query.filter_by(username=username).first().totp_secret
    client.post("/2fa/setup", data={"code": pyotp.TOTP(secret).now()}, follow_redirects=True)


def _upload_sample(client, filename="cycle.fit"):
    data = {"fit_file": (io.BytesIO(SAMPLE_FIT.read_bytes()), filename)}
    return client.post(
        "/upload", data=data, content_type="multipart/form-data", follow_redirects=True
    )


def test_upload_creates_record_and_file(client, app):
    _signup(client, app, "alice")
    resp = _upload_sample(client)
    assert resp.status_code == 200
    assert b"uploaded cycle.fit" in resp.data.lower()

    with app.app_context():
        files = FitFile.query.all()
        assert len(files) == 1
        fit = files[0]
        assert fit.original_filename == "cycle.fit"
        assert fit.point_count > 0
        # The bytes really landed on disk under the user's directory.
        stored = Path(app.config["UPLOAD_DIR"]) / str(fit.user_id) / fit.stored_name
        assert stored.exists()


def test_non_fit_upload_rejected(client, app):
    _signup(client, app, "alice")
    data = {"fit_file": (io.BytesIO(b"not a fit file"), "notes.txt")}
    resp = client.post(
        "/upload", data=data, content_type="multipart/form-data", follow_redirects=True
    )
    assert b"only .fit files" in resp.data.lower()
    with app.app_context():
        assert FitFile.query.count() == 0


def test_files_are_private_per_user(client, app):
    # Alice uploads a file.
    _signup(client, app, "alice")
    _upload_sample(client)
    with app.app_context():
        alice_file = FitFile.query.first()
        alice_file_id = alice_file.id
    client.post("/logout")

    # Bob logs in: he sees none of Alice's files on his dashboard...
    _signup(client, app, "bob")
    dash = client.get("/")
    assert b"cycle.fit" not in dash.data

    # ...and cannot reach Alice's file by id (ownership-scoped 404).
    assert client.get(f"/files/{alice_file_id}/view").status_code == 404
    assert client.get(f"/files/{alice_file_id}/image.png").status_code == 404
    assert client.post(f"/files/{alice_file_id}/delete").status_code == 404


def test_render_endpoint_returns_png(client, app, monkeypatch):
    # Avoid the network: fake the library render to write a small PNG.
    import webapp.storage as storage

    def fake_fit_to_image(source, output_path=None, *, options=None, tile_provider=None):
        img = Image.new("RGBA", (64, 48), (10, 20, 30, 255))
        if output_path is not None:
            img.save(output_path)
        return img

    monkeypatch.setattr(storage, "fit_to_image", fake_fit_to_image)

    _signup(client, app, "alice")
    _upload_sample(client)
    with app.app_context():
        file_id = FitFile.query.first().id

    resp = client.get(f"/files/{file_id}/image.png")
    assert resp.status_code == 200
    assert resp.mimetype == "image/png"
    img = Image.open(io.BytesIO(resp.data))
    assert img.size == (64, 48)


def test_delete_removes_record_and_files(client, app):
    _signup(client, app, "alice")
    _upload_sample(client)
    with app.app_context():
        fit = FitFile.query.first()
        file_id = fit.id
        stored = Path(app.config["UPLOAD_DIR"]) / str(fit.user_id) / fit.stored_name
    assert stored.exists()

    client.post(f"/files/{file_id}/delete", follow_redirects=True)
    with app.app_context():
        assert FitFile.query.count() == 0
    assert not stored.exists()


def test_upload_requires_login(client):
    data = {"fit_file": (io.BytesIO(b"x"), "cycle.fit")}
    resp = client.post("/upload", data=data, content_type="multipart/form-data")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]
