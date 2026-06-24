"""Flask-WTF form definitions."""

from __future__ import annotations

from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField, FileRequired
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, EqualTo, Length, Regexp


class RegisterForm(FlaskForm):
    username = StringField(
        "Username",
        validators=[
            DataRequired(),
            Length(min=3, max=80),
            Regexp(
                r"^[A-Za-z0-9_.-]+$",
                message="Use letters, numbers, and . _ - only.",
            ),
        ],
    )
    password = PasswordField(
        "Password", validators=[DataRequired(), Length(min=8, max=128)]
    )
    confirm = PasswordField(
        "Confirm password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match.")],
    )
    submit = SubmitField("Create account")


class TotpForm(FlaskForm):
    """A single 6-digit one-time code (used for enrollment and login step 2)."""

    code = StringField(
        "Authentication code",
        validators=[DataRequired(), Regexp(r"^\d{6}$", message="Enter the 6-digit code.")],
    )
    submit = SubmitField("Verify")


class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Continue")


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
