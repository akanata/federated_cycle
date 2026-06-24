"""Flask extension singletons, instantiated once and initialised in the factory."""

from __future__ import annotations

from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()

# Where anonymous users are redirected when a login is required.
login_manager.login_view = "auth.login"
login_manager.login_message_category = "error"
