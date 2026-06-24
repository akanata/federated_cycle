"""FIT file management: upload, listing (selection page), render, delete.

Single-owner app: OpenHost authenticates the compute-space owner before any
request reaches here, so there is no per-request login or ownership scoping.
"""

from __future__ import annotations

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    send_file,
    url_for,
)

from fit_route_map import parse_activity

from . import storage
from .extensions import db
from .forms import DeleteForm, UploadForm
from .models import FitFile

bp = Blueprint("files", __name__)


def _get_or_404(file_id: int) -> FitFile:
    fit = db.session.get(FitFile, file_id)
    if fit is None:
        abort(404)
    return fit


@bp.route("/", methods=["GET"])
def dashboard():
    files = FitFile.query.order_by(FitFile.uploaded_at.desc()).all()
    return render_template(
        "dashboard.html",
        files=files,
        upload_form=UploadForm(),
        delete_form=DeleteForm(),
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
