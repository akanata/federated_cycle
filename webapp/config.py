"""Application configuration.

Values are read from environment variables where it matters for security
(``SECRET_KEY``), with development-friendly defaults otherwise.
"""

from __future__ import annotations

import os
from pathlib import Path

# Repo root (two levels up from this file: webapp/ -> repo).
BASE_DIR = Path(__file__).resolve().parent.parent
INSTANCE_DIR = BASE_DIR / "instance"


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure-change-me")

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{INSTANCE_DIR / 'app.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Where uploaded FIT files and rendered PNGs live (one sub-dir per user).
    UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", INSTANCE_DIR / "uploads"))

    # Reject uploads larger than this (bytes). FIT files are small; 16 MiB is ample.
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", 16 * 1024 * 1024))

    # Issuer label shown in the user's authenticator app.
    TOTP_ISSUER = os.environ.get("TOTP_ISSUER", "FederatedCycle")

    # Tile source for rendering. Overridable so tests can avoid the network.
    TILE_URL = os.environ.get(
        "TILE_URL", "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
    )
    TILE_CACHE_DIR = Path(os.environ.get("TILE_CACHE_DIR", INSTANCE_DIR / "tile_cache"))

    # Session cookie hardening.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"


class TestConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False  # Simplifies form posting in tests.
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SECRET_KEY = "test-secret"
