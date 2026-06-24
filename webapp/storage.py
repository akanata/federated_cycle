"""Filesystem storage for FIT files and their rendered images.

All paths are derived from the owning user's id and a server-generated UUID, so
user-supplied names never influence the location on disk (no path traversal).
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Optional

from flask import current_app

from fit_route_map import RouteMapOptions, fit_to_image
from fit_route_map.tiles import TileProvider


def _upload_root() -> Path:
    return Path(current_app.config["UPLOAD_DIR"])


def user_dir(user_id: int) -> Path:
    path = _upload_root() / str(user_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def new_stored_name() -> str:
    return f"{uuid.uuid4().hex}.fit"


def fit_path(user_id: int, stored_name: str) -> Path:
    return user_dir(user_id) / stored_name


def render_cache_path(user_id: int, stored_name: str) -> Path:
    # Same basename as the FIT file, with a .png extension.
    return user_dir(user_id) / (Path(stored_name).stem + ".png")


def save_upload(user_id: int, file_storage) -> Path:
    """Persist an uploaded ``werkzeug`` FileStorage and return its path."""

    stored_name = new_stored_name()
    path = fit_path(user_id, stored_name)
    file_storage.save(path)
    return path


def _tile_provider() -> TileProvider:
    return TileProvider(
        url_template=current_app.config["TILE_URL"],
        cache_dir=current_app.config["TILE_CACHE_DIR"],
    )


def render_file(
    user_id: int, stored_name: str, options: Optional[RouteMapOptions] = None
) -> Path:
    """Render a stored FIT file to a cached PNG and return the PNG path.

    If a cached render already exists it is reused, avoiding repeat tile fetches.
    """

    source = fit_path(user_id, stored_name)
    cache = render_cache_path(user_id, stored_name)
    if cache.exists():
        return cache

    fit_to_image(
        source,
        cache,
        options=options or RouteMapOptions(),
        tile_provider=_tile_provider(),
    )
    return cache


def delete_file(user_id: int, stored_name: str) -> None:
    """Remove the FIT file and any cached render. Missing files are ignored."""

    fit_path(user_id, stored_name).unlink(missing_ok=True)
    render_cache_path(user_id, stored_name).unlink(missing_ok=True)
