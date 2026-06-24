"""Authentication: registration, mandatory TOTP enrollment, two-step login."""

from __future__ import annotations

import base64
import io

import pyotp
import qrcode
from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user

from .extensions import db, login_manager
from .forms import LoginForm, RegisterForm, TotpForm
from .models import User

bp = Blueprint("auth", __name__)

# Session keys for the multi-step flows (a user id that is not yet authenticated).
PENDING_ENROLL = "pending_enroll_user_id"
PENDING_LOGIN = "pending_login_user_id"


@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(User, int(user_id))


def _totp_qr_data_uri(user: User) -> str:
    """Return a base64 data URI for the otpauth provisioning QR code."""

    uri = pyotp.TOTP(user.totp_secret).provisioning_uri(
        name=user.username, issuer_name=current_app.config["TOTP_ISSUER"]
    )
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("files.dashboard"))

    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter_by(username=form.username.data).first():
            flash("That username is taken.", "error")
        else:
            user = User(
                username=form.username.data,
                totp_secret=pyotp.random_base32(),
                totp_confirmed=False,
            )
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            # Begin mandatory 2FA enrollment for the new account.
            session[PENDING_ENROLL] = user.id
            return redirect(url_for("auth.twofa_setup"))
    return render_template("register.html", form=form)


@bp.route("/2fa/setup", methods=["GET", "POST"])
def twofa_setup():
    user_id = session.get(PENDING_ENROLL)
    user = db.session.get(User, user_id) if user_id else None
    if user is None:
        flash("Start by creating an account.", "error")
        return redirect(url_for("auth.register"))

    form = TotpForm()
    if form.validate_on_submit():
        if pyotp.TOTP(user.totp_secret).verify(form.code.data, valid_window=1):
            user.totp_confirmed = True
            db.session.commit()
            session.pop(PENDING_ENROLL, None)
            login_user(user)
            flash("Two-factor authentication is set up. You're logged in.", "success")
            return redirect(url_for("files.dashboard"))
        flash("That code didn't match. Try again.", "error")

    return render_template(
        "twofa_setup.html",
        form=form,
        secret=user.totp_secret,
        qr_data_uri=_totp_qr_data_uri(user),
    )


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("files.dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash("Invalid username or password.", "error")
        elif not user.totp_confirmed:
            # Account never finished enrollment; resume it.
            session[PENDING_ENROLL] = user.id
            return redirect(url_for("auth.twofa_setup"))
        else:
            # Password OK — defer authentication until the TOTP step.
            session[PENDING_LOGIN] = user.id
            return redirect(url_for("auth.login_verify"))
    return render_template("login.html", form=form)


@bp.route("/login/verify", methods=["GET", "POST"])
def login_verify():
    user_id = session.get(PENDING_LOGIN)
    user = db.session.get(User, user_id) if user_id else None
    if user is None:
        return redirect(url_for("auth.login"))

    form = TotpForm()
    if form.validate_on_submit():
        if pyotp.TOTP(user.totp_secret).verify(form.code.data, valid_window=1):
            session.pop(PENDING_LOGIN, None)
            login_user(user)
            flash("Welcome back.", "success")
            next_url = request.args.get("next")
            return redirect(next_url or url_for("files.dashboard"))
        flash("Invalid authentication code.", "error")
    return render_template("login_verify.html", form=form)


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You've been logged out.", "success")
    return redirect(url_for("auth.login"))
