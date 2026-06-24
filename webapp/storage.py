"""Filesystem storage for FIT files and their rendered images.

Single-owner: all files live under one upload directory. On-disk names are
server-generated UUIDs, so user-supplied names never influence the path (no
traversal).
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Optional

from flask import current_app

from fit_route_map import RouteMapOptions, fit_to_image
from fit_route_map.tiles import TileProvider


def upload_dir() -> Path:
    path = Path(current_app.config["UPLOAD_DIR"])
    path.mkdir(parents=True, exist_ok=True)
    return path


def new_stored_name() -> str:
    return f"{uuid.uuid4().hex}.fit"


def fit_path(stored_name: str) -> Path:
    return upload_dir() / stored_name


def render_cache_path(stored_name: str) -> Path:
    # Same basename as the FIT file, with a .png extension.
    return upload_dir() / (Path(stored_name).stem + ".png")


def save_upload(file_storage) -> Path:
    """Persist an uploaded werkzeug FileStorage and return its path."""

    path = fit_path(new_stored_name())
    file_storage.save(path)
    return path


def _tile_provider() -> TileProvider:
    return TileProvider(
        url_template=current_app.config["TILE_URL"],
        cache_dir=current_app.config["TILE_CACHE_DIR"],
    )


def render_file(stored_name: str, options: Optional[RouteMapOptions] = None) -> Path:
    """Render a stored FIT file to a cached PNG and return the PNG path.

    If a cached render already exists it is reused, avoiding repeat tile fetches.
    """

    cache = render_cache_path(stored_name)
    if cache.exists():
        return cache

    fit_to_image(
        fit_path(stored_name),
        cache,
        options=options or RouteMapOptions(),
        tile_provider=_tile_provider(),
    )
    return cache


def delete_file(stored_name: str) -> None:
    """Remove the FIT file and any cached render. Missing files are ignored."""

    fit_path(stored_name).unlink(missing_ok=True)
    render_cache_path(stored_name).unlink(missing_ok=True)
