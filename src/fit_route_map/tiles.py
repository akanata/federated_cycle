"""Fetch and cache map tiles from an XYZ tile server."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Optional, Union

import requests
from PIL import Image

DEFAULT_TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
# OpenStreetMap's tile usage policy requires an identifying User-Agent.
DEFAULT_USER_AGENT = "fit-route-map/0.1 (+https://github.com/)"

PathLike = Union[str, Path]


class TileProvider:
    """Fetches XYZ map tiles, optionally caching them on disk.

    Parameters
    ----------
    url_template:
        XYZ URL with ``{z}``, ``{x}`` and ``{y}`` placeholders. Defaults to the
        OpenStreetMap standard tile layer. Point this at any other tile server to
        change the map style.
    user_agent:
        Sent as the ``User-Agent`` header. OSM requires a descriptive value.
    cache_dir:
        Directory used to cache downloaded tiles. ``None`` disables caching.
    session:
        An optional pre-configured :class:`requests.Session`.
    timeout:
        Per-request timeout in seconds.
    """

    def __init__(
        self,
        url_template: str = DEFAULT_TILE_URL,
        user_agent: str = DEFAULT_USER_AGENT,
        cache_dir: Optional[PathLike] = ".tile_cache",
        session: Optional[requests.Session] = None,
        timeout: float = 10.0,
    ) -> None:
        self.url_template = url_template
        self.user_agent = user_agent
        self.cache_dir = Path(cache_dir) if cache_dir is not None else None
        if self.cache_dir is not None:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.session = session or requests.Session()
        self.timeout = timeout

    def get_tile(self, x: int, y: int, z: int) -> Image.Image:
        """Return the tile at ``(x, y, z)`` as an RGBA :class:`PIL.Image.Image`."""

        data = self._get_tile_bytes(x, y, z)
        with Image.open(io.BytesIO(data)) as img:
            return img.convert("RGBA")

    def _get_tile_bytes(self, x: int, y: int, z: int) -> bytes:
        cache_path = self._cache_path(x, y, z)
        if cache_path is not None and cache_path.exists():
            return cache_path.read_bytes()

        url = self.url_template.format(z=z, x=x, y=y)
        response = self.session.get(
            url, headers={"User-Agent": self.user_agent}, timeout=self.timeout
        )
        response.raise_for_status()
        data = response.content

        if cache_path is not None:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_bytes(data)
        return data

    def _cache_path(self, x: int, y: int, z: int) -> Optional[Path]:
        if self.cache_dir is None:
            return None
        return self.cache_dir / str(z) / str(x) / f"{y}.png"
