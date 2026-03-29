from __future__ import annotations

import os
from pathlib import Path

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from .auth import auth_bp
from .extensions import db, login_manager
from .main import main_bp


def create_app() -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1, x_prefix=1)

    instance_path = Path(app.instance_path)
    instance_path.mkdir(parents=True, exist_ok=True)

    app.config.update(
        SECRET_KEY=os.getenv("NABAZTAG_PORTAL_SECRET_KEY", "dev-secret-change-me"),
        NABAZTAG_API_BASE_URL=os.getenv("NABAZTAG_API_BASE_URL", "http://localhost:8000"),
        SQLALCHEMY_DATABASE_URI=os.getenv(
            "NABAZTAG_PORTAL_DATABASE_URL",
            f"sqlite:///{instance_path / 'portal.db'}",
        ),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Connecte-toi pour accéder à tes lapins."

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)

    with app.app_context():
        from . import models

        db.create_all()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "nabaztag-portal"}

    return app
