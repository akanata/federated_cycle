"""Database models.

The app is single-owner (OpenHost gates access to the compute-space owner), so
there is no user/account model — uploaded files all belong to that one owner.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from .extensions import db


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class FitFile(db.Model):
    __tablename__ = "fit_files"

    id = db.Column(db.Integer, primary_key=True)
    original_filename = db.Column(db.String(255), nullable=False)
    # On-disk name (a UUID + .fit) — never derived from user input.
    stored_name = db.Column(db.String(64), unique=True, nullable=False)
    size_bytes = db.Column(db.Integer, nullable=False)
    point_count = db.Column(db.Integer, nullable=False, default=0)
    # Cached from the FIT session for cheap Workout listing/filtering and sorting.
    sport = db.Column(db.String(32), nullable=True)
    started_at = db.Column(db.DateTime, nullable=True)
    distance_m = db.Column(db.Float, nullable=True)  # total ride distance (metres)
    intensity = db.Column(db.Float, nullable=True)  # HR-zone-weighted effort score
    uploaded_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
