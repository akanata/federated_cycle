"""High-level convenience API."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

from PIL import Image

from .parser import parse_fit
from .renderer import RouteMapOptions, render_route
from .tiles import TileProvider

PathLike = Union[str, Path]

_JPEG_SUFFIXES = {".jpg", ".jpeg"}


def fit_to_image(
    fit_path: PathLike,
    output_path: Optional[PathLike] = None,
    *,
    options: Optional[RouteMapOptions] = None,
    tile_provider: Optional[TileProvider] = None,
) -> Image.Image:
    """Parse a FIT file and render its route onto a map image.

    Parameters
    ----------
    fit_path:
        Path to the input ``.fit`` file.
    output_path:
        Where to save the rendered image. The format is inferred from the file
        extension. If ``None``, nothing is written and only the image is returned.
    options:
        Styling/sizing options (see :class:`RouteMapOptions`).
    tile_provider:
        A configured :class:`TileProvider`. Defaults to OpenStreetMap tiles.

    Returns
    -------
    PIL.Image.Image
        The rendered RGBA image.

    Raises
    ------
    ValueError
        If the FIT file contains no GPS track points.
    """

    points = parse_fit(fit_path)
    if not points:
        raise ValueError(f"No GPS track points found in {fit_path}")

    image = render_route(points, tile_provider=tile_provider, options=options)

    if output_path is not None:
        output_path = Path(output_path)
        to_save = image
        if output_path.suffix.lower() in _JPEG_SUFFIXES:
            to_save = image.convert("RGB")  # JPEG has no alpha channel.
        to_save.save(output_path)

    return image
