"""Flask application factory for the FIT route-rendering web app."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Type

from flask import Flask
from sqlalchemy.exc import OperationalError

from .config import Config
from .extensions import csrf, db, login_manager


def create_app(config: Optional[Type[Config]] = None) -> Flask:
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(config or Config)

    _ensure_dirs(app)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    from . import models  # noqa: F401  (register models with SQLAlchemy)
    from .auth import bp as auth_bp
    from .files import bp as files_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(files_bp)

    with app.app_context():
        _init_db()

    return app


def _init_db() -> None:
    """Create tables if missing, tolerating a cross-process first-boot race.

    Under multiple gunicorn workers, two processes can both find an empty SQLite
    file and race to ``CREATE TABLE``; the loser sees "table already exists". The
    desired state (tables present) still holds, so that specific error is ignored
    while anything else (e.g. a permissions/disk problem) is re-raised.
    """

    try:
        db.create_all()
    except OperationalError as exc:
        if "already exists" not in str(exc).lower():
            raise


def _ensure_dirs(app: Flask) -> None:
    """Create the instance, upload, and tile-cache directories if missing."""

    for key in ("UPLOAD_DIR", "TILE_CACHE_DIR"):
        value = app.config.get(key)
        if value:
            Path(value).mkdir(parents=True, exist_ok=True)

    uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    prefix = "sqlite:///"
    if uri.startswith(prefix):
        db_path = uri[len(prefix):]
        if db_path and db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
