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

## Web app (OpenHost)

A Flask app (`webapp/`) wraps the library and is designed to run on
[OpenHost](https://imbue-openhost.github.io/openhost/), which handles identity at the
platform layer. It is **single-owner** — OpenHost authenticates the compute-space owner, so
the app has no accounts/login of its own.

- **Upload + render** — a dashboard form uploads `.fit` files; each ride has a Render action
  showing the route-over-map image. Files are stored under the owner's persistent data dir.
- **Workout provider** — the app registers as a provider of OpenHost's
  [health-data service](https://github.com/imbue-openhost/health-data-service-spec) and serves
  each uploaded FIT file as a **Workout** (a cycling ride becomes a `CyclingWorkout`, with the
  GPS track as a GPX 1.1 `route_gpx` and heart-rate/distance/speed/elevation metrics).

### Deploy on OpenHost

`openhost.toml` declares the container, persistent storage, and the provided service:

```toml
[[services.v2.provides]]
service = "github.com/imbue-openhost/openhost/services/health-data"
version = "0.1.0"
endpoint = "/api/"
```

```bash
oh app deploy https://github.com/akanata/federated_cycle --wait
```

OpenHost injects `OPENHOST_APP_DATA_DIR`, `OPENHOST_SQLITE_MAIN`, `OPENHOST_OWNER_USERNAME`
and `OPENHOST_APP_NAME`, which the app reads automatically.

### Provider API

Consumer apps reach these through the OpenHost router (auth handled by the platform):

| Endpoint | Returns |
|----------|---------|
| `GET /api/v1/workouts` | all rides as Workouts (filters: `workout_type,start,end,limit`) |
| `GET /api/v1/workouts/{id}` | one ride (by FIT-file id) |
| `GET /api/v1/metrics` | the metric catalog this provider serves |
| `GET /api/v1/time-series`, `/api/v1/sleep-sessions` | `[]` (not held here) |

### Run locally

```bash
pip install -e ".[web]"
SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')" python -m webapp
# open http://127.0.0.1:5000 ; Workouts at /api/v1/workouts
```

Or via Docker (gunicorn, non-root, healthcheck); data persists in a named volume:

```bash
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
docker compose up --build      # http://localhost:5000
```

> The health-data spec is still in design; the Workout JSON is hand-rolled to match its
> documented field names and is covered by tests, so any spec changes are localized to
> `webapp/workouts.py`.

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
