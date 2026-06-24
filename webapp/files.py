"""FIT file management: upload, listing (selection page), render, delete.

Single-owner app: OpenHost authenticates the compute-space owner before any
request reaches here, so there is no per-request login or ownership scoping.
"""

from __future__ import annotations

from datetime import timezone

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

from fit_route_map import parse_activity

from . import storage
from .analysis import hr_zone_intensity
from .extensions import db
from .forms import DeleteForm, UploadForm
from .models import FitFile

bp = Blueprint("files", __name__)

# (key, label) pairs shown as the dashboard sort controls.
SORT_OPTIONS = [
    ("latest", "Latest"),
    ("earliest", "Earliest"),
    ("short_long", "Short → Long"),
    ("long_short", "Long → Short"),
    ("most_intense", "Most intense"),
    ("most_chill", "Most chill"),
]
DEFAULT_SORT = "latest"


def _ride_ts(f: FitFile) -> float:
    """Ride date as an epoch float (started_at, else upload time); 0 if unknown."""

    dt = f.started_at or f.uploaded_at
    if dt is None:
        return 0.0
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


# key -> (sort value, reverse?). distance_m/intensity are floats after backfill.
_SORT_KEYS = {
    "short_long": (lambda f: f.distance_m or 0.0, False),
    "long_short": (lambda f: f.distance_m or 0.0, True),
    "most_intense": (lambda f: f.intensity or 0.0, True),
    "most_chill": (lambda f: f.intensity or 0.0, False),
    "latest": (_ride_ts, True),
    "earliest": (_ride_ts, False),
}


def _get_or_404(file_id: int) -> FitFile:
    fit = db.session.get(FitFile, file_id)
    if fit is None:
        abort(404)
    return fit


def _backfill_metrics(files: list[FitFile]) -> None:
    """Populate distance_m/intensity for any rows missing them (e.g. older uploads).

    New uploads compute these up front; this catches rows created before the
    columns existed. Each file is parsed at most once, then the values persist.
    """

    dirty = False
    max_hr = current_app.config["MAX_HR"]
    for f in files:
        if f.distance_m is not None and f.intensity is not None:
            continue
        try:
            activity = parse_activity(storage.fit_path(f.stored_name))
            f.distance_m = activity.summary.total_distance or 0.0
            f.intensity = hr_zone_intensity(activity.heart_rate, max_hr)
        except Exception:
            f.distance_m = f.distance_m or 0.0
            f.intensity = f.intensity or 0.0
        dirty = True
    if dirty:
        db.session.commit()


@bp.route("/", methods=["GET"])
def dashboard():
    sort = request.args.get("sort", DEFAULT_SORT)
    if sort not in _SORT_KEYS:
        sort = DEFAULT_SORT

    files = FitFile.query.all()
    _backfill_metrics(files)
    key_fn, reverse = _SORT_KEYS[sort]
    files.sort(key=key_fn, reverse=reverse)

    return render_template(
        "dashboard.html",
        files=files,
        upload_form=UploadForm(),
        delete_form=DeleteForm(),
        sort=sort,
        sort_options=SORT_OPTIONS,
    )


@bp.route("/upload", methods=["POST"])
def upload():
    form = UploadForm()
    if not form.validate_on_submit():
        for errors in form.errors.values():
            for error in errors:
                flash(error, "error")
        return redirect(url_for("files.dashboard"))

    file_storage = form.fit_file.data
    path = storage.save_upload(file_storage)

    # Validate the upload actually contains a GPS track before keeping it, and
    # cache the sport/start time for cheap Workout listing.
    try:
        activity = parse_activity(path)
    except Exception:
        path.unlink(missing_ok=True)
        flash("That file could not be read as a FIT activity.", "error")
        return redirect(url_for("files.dashboard"))

    if not activity.track:
        path.unlink(missing_ok=True)
        flash("That FIT file has no GPS track to render.", "error")
        return redirect(url_for("files.dashboard"))

    fit = FitFile(
        original_filename=file_storage.filename,
        stored_name=path.name,
        size_bytes=path.stat().st_size,
        point_count=len(activity.track),
        sport=activity.summary.sport,
        started_at=activity.summary.start_time,
        distance_m=activity.summary.total_distance or 0.0,
        intensity=hr_zone_intensity(activity.heart_rate, current_app.config["MAX_HR"]),
    )
    db.session.add(fit)
    db.session.commit()
    flash(f"Uploaded {fit.original_filename} ({fit.point_count} points).", "success")
    return redirect(url_for("files.dashboard"))


@bp.route("/files/<int:file_id>/image.png", methods=["GET"])
def render_image(file_id: int):
    fit = _get_or_404(file_id)
    try:
        png_path = storage.render_file(fit.stored_name)
    except Exception:
        abort(502, "Could not render the route (map tiles unavailable?).")
    return send_file(png_path, mimetype="image/png")


@bp.route("/files/<int:file_id>/view", methods=["GET"])
def view(file_id: int):
    fit = _get_or_404(file_id)
    return render_template("view.html", file=fit)


@bp.route("/files/<int:file_id>/delete", methods=["POST"])
def delete(file_id: int):
    fit = _get_or_404(file_id)
    form = DeleteForm()
    if form.validate_on_submit():
        storage.delete_file(fit.stored_name)
        db.session.delete(fit)
        db.session.commit()
        flash("File deleted.", "success")
    return redirect(url_for("files.dashboard"))
