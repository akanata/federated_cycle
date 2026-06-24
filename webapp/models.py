"""Database models."""

from __future__ import annotations

from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    # Base32 TOTP secret. Stored plaintext for v1 (see README security notes).
    totp_secret = db.Column(db.String(64), nullable=False)
    totp_confirmed = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    files = db.relationship(
        "FitFile", back_populates="owner", cascade="all, delete-orphan"
    )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class FitFile(db.Model):
    __tablename__ = "fit_files"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    original_filename = db.Column(db.String(255), nullable=False)
    # On-disk name (a UUID + .fit) — never derived from user input.
    stored_name = db.Column(db.String(64), unique=True, nullable=False)
    size_bytes = db.Column(db.Integer, nullable=False)
    point_count = db.Column(db.Integer, nullable=False, default=0)
    uploaded_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    owner = db.relationship("User", back_populates="files")
