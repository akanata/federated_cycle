"""Flask extension singletons, instantiated once and initialised in the factory."""

from __future__ import annotations

from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect

db = SQLAlchemy()
csrf = CSRFProtect()
