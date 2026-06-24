"""Flask-WTF form definitions."""

from __future__ import annotations

from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField, FileRequired
from wtforms import SubmitField


class UploadForm(FlaskForm):
    fit_file = FileField(
        "FIT file",
        validators=[
            FileRequired(),
            FileAllowed(["fit"], "Only .fit files are allowed."),
        ],
    )
    submit = SubmitField("Upload")


class DeleteForm(FlaskForm):
    """CSRF-protected empty form for destructive POST actions."""

    submit = SubmitField("Delete")
