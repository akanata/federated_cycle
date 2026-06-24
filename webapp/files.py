"""FIT file management: upload, listing (selection page), render, delete."""

from __future__ import annotations

import os

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    send_file,
    url_for,
)
from flask_login import current_user, login_required

from fit_route_map import parse_fit

from . import storage
from .extensions import db
from .forms import DeleteForm, UploadForm
from .models import FitFile

bp = Blueprint("files", __name__)


def _owned_or_404(file_id: int) -> FitFile:
    """Fetch a FitFile by id, but only if it belongs to the current user."""

    fit = db.session.get(FitFile, file_id)
    if fit is None or fit.user_id != current_user.id:
        abort(404)
    return fit


@bp.route("/", methods=["GET"])
@login_required
def dashboard():
    files = (
        FitFile.query.filter_by(user_id=current_user.id)
        .order_by(FitFile.uploaded_at.desc())
        .all()
    )
    return render_template(
        "dashboard.html",
        files=files,
        upload_form=UploadForm(),
        delete_form=DeleteForm(),
    )


@bp.route("/upload", methods=["POST"])
@login_required
def upload():
    form = UploadForm()
    if not form.validate_on_submit():
        for errors in form.errors.values():
            for error in errors:
                flash(error, "error")
        return redirect(url_for("files.dashboard"))

    file_storage = form.fit_file.data
    path = storage.save_upload(current_user.id, file_storage)

    # Validate the upload actually contains a GPS track before keeping it.
    try:
        points = parse_fit(path)
    except Exception:
        path.unlink(missing_ok=True)
        flash("That file could not be read as a FIT activity.", "error")
        return redirect(url_for("files.dashboard"))

    if not points:
        path.unlink(missing_ok=True)
        flash("That FIT file has no GPS track to render.", "error")
        return redirect(url_for("files.dashboard"))

    fit = FitFile(
        user_id=current_user.id,
        original_filename=file_storage.filename,
        stored_name=path.name,
        size_bytes=path.stat().st_size,
        point_count=len(points),
    )
    db.session.add(fit)
    db.session.commit()
    flash(f"Uploaded {fit.original_filename} ({fit.point_count} points).", "success")
    return redirect(url_for("files.dashboard"))


@bp.route("/files/<int:file_id>/image.png", methods=["GET"])
@login_required
def render_image(file_id: int):
    fit = _owned_or_404(file_id)
    try:
        png_path = storage.render_file(current_user.id, fit.stored_name)
    except Exception:
        abort(502, "Could not render the route (map tiles unavailable?).")
    return send_file(png_path, mimetype="image/png")


@bp.route("/files/<int:file_id>/view", methods=["GET"])
@login_required
def view(file_id: int):
    fit = _owned_or_404(file_id)
    return render_template("view.html", file=fit)


@bp.route("/files/<int:file_id>/delete", methods=["POST"])
@login_required
def delete(file_id: int):
    fit = _owned_or_404(file_id)
    form = DeleteForm()
    if form.validate_on_submit():
        storage.delete_file(current_user.id, fit.stored_name)
        db.session.delete(fit)
        db.session.commit()
        flash("File deleted.", "success")
    return redirect(url_for("files.dashboard"))
