"""Render the bundled sample activity to a PNG.

Run from the project root after installing the package::

    python examples/render_example.py

This fetches OpenStreetMap tiles, so it needs network access. Tiles are cached in
``.tile_cache/`` so subsequent runs are fast.
"""

from pathlib import Path

from fit_route_map import RouteMapOptions, fit_to_image

HERE = Path(__file__).resolve().parent


def main() -> None:
    fit_path = HERE / "cycle.fit"
    out_path = HERE / "cycle.png"

    options = RouteMapOptions(width=1280, height=960, line_width=5)
    image = fit_to_image(fit_path, out_path, options=options)

    print(f"Wrote {out_path} ({image.size[0]}x{image.size[1]})")


if __name__ == "__main__":
    main()
