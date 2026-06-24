"""Flask application factory for the FIT route-rendering / Workout-provider app."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Type

from flask import Flask
from sqlalchemy.exc import OperationalError

from .config import Config
from .extensions import csrf, db


def create_app(config: Optional[Type[Config]] = None) -> Flask:
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(config or Config)

    _ensure_dirs(app)

    db.init_app(app)
    csrf.init_app(app)
    # Service (provider) endpoints are GET-only JSON; exempt them from CSRF.
    from .service import bp as service_bp

    csrf.exempt(service_bp)

    from . import models  # noqa: F401  (register models with SQLAlchemy)
    from .files import bp as files_bp

    app.register_blueprint(files_bp)
    app.register_blueprint(service_bp)

    with app.app_context():
        _init_db()
        _migrate_schema()

    return app


def _migrate_schema() -> None:
    """Add columns introduced after a deployment's DB was first created.

    We use ``create_all`` (no migration framework), so new model columns must be
    back-filled onto an existing SQLite table with ``ALTER TABLE ADD COLUMN``.
    Idempotent and safe under concurrent workers (ignores duplicate-column races).
    """

    from sqlalchemy import inspect, text

    inspector = inspect(db.engine)
    if "fit_files" not in inspector.get_table_names():
        return
    existing = {c["name"] for c in inspector.get_columns("fit_files")}
    for column, ddl in (("distance_m", "FLOAT"), ("intensity", "FLOAT")):
        if column in existing:
            continue
        try:
            with db.engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE fit_files ADD COLUMN {column} {ddl}"))
        except OperationalError as exc:
            if "duplicate column" not in str(exc).lower():
                raise


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
    """Create the upload, tile-cache, and database directories if missing."""

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
