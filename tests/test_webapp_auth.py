import pyotp
import pytest

from webapp import create_app
from webapp.config import TestConfig
from webapp.extensions import db
from webapp.models import User


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


def _secret_for(app, username):
    with app.app_context():
        return User.query.filter_by(username=username).first().totp_secret


def register(client, username="alice", password="hunter2pass"):
    return client.post(
        "/register",
        data={"username": username, "password": password, "confirm": password},
        follow_redirects=True,
    )


def enroll(client, app, username="alice"):
    """Complete mandatory TOTP enrollment for a freshly registered user."""
    secret = _secret_for(app, username)
    code = pyotp.TOTP(secret).now()
    client.post("/2fa/setup", data={"code": code}, follow_redirects=True)
    return secret


def test_register_redirects_to_2fa_setup(client, app):
    resp = register(client)
    assert resp.status_code == 200
    assert b"two-factor" in resp.data.lower()
    with app.app_context():
        user = User.query.filter_by(username="alice").first()
        assert user is not None
        assert user.totp_confirmed is False


def test_enrollment_confirms_totp_and_logs_in(client, app):
    register(client)
    enroll(client, app)
    with app.app_context():
        assert User.query.filter_by(username="alice").first().totp_confirmed is True
    # Now authenticated: dashboard is reachable.
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 200


def test_wrong_enrollment_code_rejected(client, app):
    register(client)
    resp = client.post("/2fa/setup", data={"code": "000000"}, follow_redirects=True)
    assert b"didn&#39;t match" in resp.data or b"didn't match" in resp.data
    with app.app_context():
        assert User.query.filter_by(username="alice").first().totp_confirmed is False


def test_full_two_step_login(client, app):
    register(client)
    secret = enroll(client, app)
    client.post("/logout")

    # Step 1: password.
    resp = client.post(
        "/login",
        data={"username": "alice", "password": "hunter2pass"},
        follow_redirects=True,
    )
    assert b"authentication code" in resp.data.lower()
    # Not yet authenticated until the second factor.
    assert client.get("/", follow_redirects=False).status_code == 302

    # Step 2: TOTP.
    code = pyotp.TOTP(secret).now()
    resp = client.post("/login/verify", data={"code": code}, follow_redirects=True)
    assert resp.status_code == 200
    assert client.get("/", follow_redirects=False).status_code == 200


def test_login_wrong_password_rejected(client, app):
    register(client)
    enroll(client, app)
    client.post("/logout")
    resp = client.post(
        "/login",
        data={"username": "alice", "password": "wrongpass1"},
        follow_redirects=True,
    )
    assert b"invalid username or password" in resp.data.lower()


def test_login_wrong_totp_rejected(client, app):
    register(client)
    enroll(client, app)
    client.post("/logout")
    client.post("/login", data={"username": "alice", "password": "hunter2pass"})
    resp = client.post("/login/verify", data={"code": "000000"}, follow_redirects=True)
    assert b"invalid authentication code" in resp.data.lower()
    assert client.get("/", follow_redirects=False).status_code == 302


def test_protected_dashboard_redirects_when_anonymous(client):
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_duplicate_username_rejected(client, app):
    register(client)
    resp = register(client)
    assert b"taken" in resp.data.lower()
