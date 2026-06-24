"""Application configuration.

When running on OpenHost the platform injects ``OPENHOST_*`` environment variables
(persistent data dir, provisioned SQLite path, owner name); locally those are
absent and we fall back to an ``instance/`` directory under the repo.
"""

from __future__ import annotations

import os
from pathlib import Path

# Repo root (one level up from this file: webapp/ -> repo).
BASE_DIR = Path(__file__).resolve().parent.parent
INSTANCE_DIR = BASE_DIR / "instance"

# OpenHost-provided locations, when present.
_APP_DATA_DIR = os.environ.get("OPENHOST_APP_DATA_DIR")
_SQLITE_MAIN = os.environ.get("OPENHOST_SQLITE_MAIN")

_DATA_ROOT = Path(_APP_DATA_DIR) if _APP_DATA_DIR else INSTANCE_DIR


def _default_db_uri() -> str:
    if _SQLITE_MAIN:  # OpenHost-provisioned database file.
        return f"sqlite:///{_SQLITE_MAIN}"
    return f"sqlite:///{_DATA_ROOT / 'app.db'}"


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure-change-me")

    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", _default_db_uri())
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Wait up to 15s for SQLite write locks instead of failing instantly, so
    # concurrent gunicorn workers don't hit "database is locked".
    SQLALCHEMY_ENGINE_OPTIONS = {"connect_args": {"timeout": 15}}

    # Where uploaded FIT files and rendered PNGs live.
    UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", _DATA_ROOT / "uploads"))

    # Reject uploads larger than this (bytes). FIT files are small; 16 MiB is ample.
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", 16 * 1024 * 1024))

    # Tile source for rendering. Overridable so tests can avoid the network.
    TILE_URL = os.environ.get(
        "TILE_URL", "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
    )
    TILE_CACHE_DIR = Path(os.environ.get("TILE_CACHE_DIR", _DATA_ROOT / "tile_cache"))

    # Display name of the compute-space owner (OpenHost injects this).
    OWNER_USERNAME = os.environ.get("OPENHOST_OWNER_USERNAME", "owner")

    # Identifies this app as the data source in emitted Workouts.
    WORKOUT_SOURCE = os.environ.get("OPENHOST_APP_NAME", "fit-route-map")

    # Reference max heart rate for zone-based intensity (used to sort rides).
    MAX_HR = float(os.environ.get("MAX_HR", "190"))

    # Session cookie hardening.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"

    # Behind OpenHost's router the app sees HTTPS but a forwarded internal Host,
    # so Flask-WTF's strict Referer/host origin check rejects valid POSTs. Disable
    # just that check; token-based CSRF validation (form field vs session) stays on.
    WTF_CSRF_SSL_STRICT = False


class TestConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False  # Simplifies form posting in tests.
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SECRET_KEY = "test-secret"
