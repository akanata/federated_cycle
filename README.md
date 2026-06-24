# fit-route-map

Convert a **FIT** activity file (Garmin, Wahoo, etc.) into an image of the recorded
route drawn over an **OpenStreetMap** background.

```
FIT file  ──parse──▶  GPS track  ──project + stitch tiles + draw──▶  PNG
```

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"      # editable install with test deps
```

Dependencies: [`fitparse`](https://github.com/dtcooper/python-fitparse),
[`Pillow`](https://python-pillow.org/), [`requests`](https://requests.readthedocs.io/).

## Usage

```python
from fit_route_map import fit_to_image

# Simplest case: read a FIT file and write a PNG.
fit_to_image("ride.fit", "ride.png")
```

Customise the size and styling:

```python
from fit_route_map import fit_to_image, RouteMapOptions

options = RouteMapOptions(
    width=1280,
    height=960,
    line_color=(224, 26, 79, 255),   # RGBA route colour
    line_width=5,
    show_markers=True,               # green start dot, dark end dot
)
image = fit_to_image("ride.fit", "ride.png", options=options)
print(image.size)                    # also returns the PIL.Image
```

Use a different tile server (any XYZ layer works):

```python
from fit_route_map import fit_to_image, TileProvider

provider = TileProvider(
    url_template="https://tile.opentopomap.org/{z}/{x}/{y}.png",
    user_agent="my-app/1.0 (you@example.com)",
    cache_dir=".tile_cache",
)
fit_to_image("ride.fit", "ride.png", tile_provider=provider)
```

### Lower-level API

```python
from fit_route_map import parse_fit, render_route

points = parse_fit("ride.fit")       # list[TrackPoint] with lat/lon/altitude/timestamp
image = render_route(points)         # PIL.Image
```

## Try it

A sample ride is included:

```bash
python examples/render_example.py    # writes examples/cycle.png
```

## How it works

- **`parser`** reads the FIT `record` messages and converts positions from FIT
  *semicircles* to degrees (`degrees = semicircles × 180 / 2³¹`).
- **`geo`** projects lon/lat to Web Mercator pixel coordinates and picks the largest
  zoom level at which the whole route fits the requested image size.
- **`tiles`** downloads the needed XYZ map tiles (with an on-disk cache and an
  OSM-compliant `User-Agent`).
- **`renderer`** stitches the tiles into the canvas, draws the route polyline, and
  adds start/end markers.

## Web app

A multi-user Flask app (`webapp/`) wraps the library so users can log in, store their
own FIT files privately, and render routes from the browser.

- **Accounts with 2FA** — registration enrolls a mandatory TOTP authenticator
  (Google Authenticator, Authy, 1Password…); login is two-step (password → 6-digit code).
- **Private per-user storage** — FIT files live under `instance/uploads/<user_id>/`, with
  metadata in a SQLite DB; every query is scoped to the logged-in user.
- **Upload + select** — a dashboard form uploads `.fit` files and lists your rides, each
  with a Render action that displays the route-over-map image.

```bash
pip install -e ".[web]"
SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')" python -m webapp
# open http://127.0.0.1:5000
```

Key settings (env vars): `SECRET_KEY`, `DATABASE_URL`, `UPLOAD_DIR`, `TILE_URL`,
`TOTP_ISSUER`, `SESSION_COOKIE_SECURE=1` (behind HTTPS in production). The app stores TOTP
secrets in the database in plaintext for now — encrypting them at rest is a planned
follow-up, along with password reset and async rendering.

### Run with Docker

The web app ships with a `Dockerfile` (gunicorn, non-root user, healthcheck) and a
`docker-compose.yml` that persists the database, uploads and tile cache in a named volume.

```bash
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
docker compose up --build      # serves on http://localhost:5000
```

`SECRET_KEY` is required — compose refuses to start without it. Put it (and optional
`TOTP_ISSUER`, `SESSION_COOKIE_SECURE=1`) in a `.env` file beside the compose file to avoid
re-exporting. Without compose:

```bash
docker build -t federated-cycle-web .
docker run -p 5000:5000 -e SECRET_KEY=... -v fitdata:/app/instance federated-cycle-web
```

## Notes

- Rendering needs network access to fetch map tiles; downloaded tiles are cached under
  `.tile_cache/` (or `instance/tile_cache/` for the web app). Please respect the
  [OSM tile usage policy](https://operations.osmfoundation.org/policies/tiles/) — set a
  descriptive `User-Agent` and avoid bulk downloads.
- Tests run fully offline (a fake tile provider and a mocked FIT reader):

  ```bash
  pytest
  ```

## License

MIT
