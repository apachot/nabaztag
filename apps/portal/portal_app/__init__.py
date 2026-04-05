from __future__ import annotations

import json
import os
from pathlib import Path

from flask import Flask
from sqlalchemy import text
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
        NABAZTAG_VL_PING_SERVER=os.getenv("NABAZTAG_VL_PING_SERVER", "nabaztag.org"),
        NABAZTAG_VL_BROAD_SERVER=os.getenv("NABAZTAG_VL_BROAD_SERVER", "nabaztag.org"),
        NABAZTAG_VL_XMPP_SERVER=os.getenv("NABAZTAG_VL_XMPP_SERVER", "nabaztag.org"),
        NABAZTAG_VL_XMPP_PORT=int(os.getenv("NABAZTAG_VL_XMPP_PORT", "5222")),
        NABAZTAG_VL_XMPP_ALT_SERVER=os.getenv("NABAZTAG_VL_XMPP_ALT_SERVER", "nabaztag.org"),
        NABAZTAG_VL_XMPP_ALT_PORT=int(os.getenv("NABAZTAG_VL_XMPP_ALT_PORT", "443")),
        NABAZTAG_VL_XMPP_TIMEOUT=int(os.getenv("NABAZTAG_VL_XMPP_TIMEOUT", "8")),
        NABAZTAG_XMPP_BIND_HOST=os.getenv("NABAZTAG_XMPP_BIND_HOST", "0.0.0.0"),
        NABAZTAG_XMPP_BIND_PORT=int(os.getenv("NABAZTAG_XMPP_BIND_PORT", "5222")),
        NABAZTAG_STT_MODEL=os.getenv("NABAZTAG_STT_MODEL", "small"),
        NABAZTAG_STT_LANGUAGE=os.getenv("NABAZTAG_STT_LANGUAGE", "fr"),
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

    @app.before_request
    def ensure_background_workers() -> None:
        from .main import ensure_auto_intervention_worker_started

        ensure_auto_intervention_worker_started(app)

    with app.app_context():
        from . import models

        db.create_all()
        _ensure_portal_schema()
        _migrate_legacy_connector_settings()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "nabaztag-portal"}

    return app


def _ensure_portal_schema() -> None:
    inspector = db.inspect(db.engine)
    rabbit_columns = {column["name"] for column in inspector.get_columns("rabbit")}
    user_columns = {column["name"] for column in inspector.get_columns("user")}
    recording_columns = {column["name"] for column in inspector.get_columns("rabbit_recording")}
    existing_tables = set(inspector.get_table_names())
    statements: list[str] = []

    if "photo_filename" not in rabbit_columns:
        statements.append("ALTER TABLE rabbit ADD COLUMN photo_filename VARCHAR(255)")
    if "photo_original_name" not in rabbit_columns:
        statements.append("ALTER TABLE rabbit ADD COLUMN photo_original_name VARCHAR(255)")
    if "personality_prompt" not in rabbit_columns:
        statements.append("ALTER TABLE rabbit ADD COLUMN personality_prompt TEXT")
    if "llm_model" not in rabbit_columns:
        statements.append("ALTER TABLE rabbit ADD COLUMN llm_model VARCHAR(64)")
    if "tts_voice" not in rabbit_columns:
        statements.append("ALTER TABLE rabbit ADD COLUMN tts_voice VARCHAR(64)")
    if "auto_performance_enabled" not in rabbit_columns:
        statements.append("ALTER TABLE rabbit ADD COLUMN auto_performance_enabled BOOLEAN DEFAULT 0")
    if "auto_performance_frequency_minutes" not in rabbit_columns:
        statements.append("ALTER TABLE rabbit ADD COLUMN auto_performance_frequency_minutes INTEGER DEFAULT 180")
    if "auto_performance_window_start" not in rabbit_columns:
        statements.append("ALTER TABLE rabbit ADD COLUMN auto_performance_window_start VARCHAR(5) DEFAULT '09:00'")
    if "auto_performance_window_end" not in rabbit_columns:
        statements.append("ALTER TABLE rabbit ADD COLUMN auto_performance_window_end VARCHAR(5) DEFAULT '21:00'")
    if "auto_performance_next_at" not in rabbit_columns:
        statements.append("ALTER TABLE rabbit ADD COLUMN auto_performance_next_at DATETIME")
    if "conversation_summary" not in rabbit_columns:
        statements.append("ALTER TABLE rabbit ADD COLUMN conversation_summary TEXT")
    if "conversation_summary_turn_id" not in rabbit_columns:
        statements.append("ALTER TABLE rabbit ADD COLUMN conversation_summary_turn_id INTEGER")
    if "alerts_last_seen_event_id" not in rabbit_columns:
        statements.append("ALTER TABLE rabbit ADD COLUMN alerts_last_seen_event_id INTEGER")
    if "openai_api_key" not in user_columns:
        statements.append("ALTER TABLE user ADD COLUMN openai_api_key TEXT")
    if "mistral_api_key" not in user_columns:
        statements.append("ALTER TABLE user ADD COLUMN mistral_api_key TEXT")
    if "home_assistant_url" not in user_columns:
        statements.append("ALTER TABLE user ADD COLUMN home_assistant_url TEXT")
    if "home_assistant_token" not in user_columns:
        statements.append("ALTER TABLE user ADD COLUMN home_assistant_token TEXT")
    if "content_sha1" not in recording_columns:
        statements.append("ALTER TABLE rabbit_recording ADD COLUMN content_sha1 VARCHAR(40)")

    for statement in statements:
        db.session.execute(text(statement))

    if statements:
        db.session.commit()

    if "mobile_app_pairing_session" not in existing_tables:
        db.session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS mobile_app_pairing_session (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    token VARCHAR(128) NOT NULL UNIQUE,
                    status VARCHAR(32) NOT NULL DEFAULT 'pending',
                    device_name VARCHAR(255),
                    expires_at DATETIME NOT NULL,
                    consumed_at DATETIME,
                    created_at DATETIME NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES user(id)
                )
                """
            )
        )
        db.session.execute(
            text("CREATE INDEX IF NOT EXISTS ix_mobile_app_pairing_session_user_id ON mobile_app_pairing_session(user_id)")
        )
        db.session.execute(
            text("CREATE INDEX IF NOT EXISTS ix_mobile_app_pairing_session_token ON mobile_app_pairing_session(token)")
        )
        db.session.commit()

    if "rabbit_app_pairing_session" not in existing_tables:
        db.session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS rabbit_app_pairing_session (
                    id INTEGER PRIMARY KEY,
                    rabbit_id INTEGER NOT NULL,
                    token VARCHAR(64) NOT NULL UNIQUE,
                    status VARCHAR(32) NOT NULL DEFAULT 'pending',
                    expires_at DATETIME NOT NULL,
                    consumed_at DATETIME,
                    created_at DATETIME NOT NULL,
                    FOREIGN KEY(rabbit_id) REFERENCES rabbit(id)
                )
                """
            )
        )
        db.session.execute(
            text("CREATE INDEX IF NOT EXISTS ix_rabbit_app_pairing_session_rabbit_id ON rabbit_app_pairing_session(rabbit_id)")
        )
        db.session.execute(
            text("CREATE INDEX IF NOT EXISTS ix_rabbit_app_pairing_session_token ON rabbit_app_pairing_session(token)")
        )
        db.session.commit()

    if "mobile_api_token" not in existing_tables:
        db.session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS mobile_api_token (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    label VARCHAR(255),
                    token_hash VARCHAR(64) NOT NULL UNIQUE,
                    last_used_at DATETIME,
                    revoked_at DATETIME,
                    created_at DATETIME NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES user(id)
                )
                """
            )
        )
        db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_mobile_api_token_user_id ON mobile_api_token(user_id)"))
        db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_mobile_api_token_token_hash ON mobile_api_token(token_hash)"))
        db.session.commit()

    if "local_bridge_pairing_session" not in existing_tables:
        db.session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS local_bridge_pairing_session (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    token VARCHAR(128) NOT NULL UNIQUE,
                    status VARCHAR(32) NOT NULL DEFAULT 'pending',
                    bridge_name VARCHAR(255),
                    expires_at DATETIME NOT NULL,
                    consumed_at DATETIME,
                    created_at DATETIME NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES user(id)
                )
                """
            )
        )
        db.session.execute(
            text("CREATE INDEX IF NOT EXISTS ix_local_bridge_pairing_session_user_id ON local_bridge_pairing_session(user_id)")
        )
        db.session.execute(
            text("CREATE INDEX IF NOT EXISTS ix_local_bridge_pairing_session_token ON local_bridge_pairing_session(token)")
        )
        db.session.commit()

    if "local_bridge" not in existing_tables:
        db.session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS local_bridge (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    token_hash VARCHAR(64) NOT NULL UNIQUE,
                    capabilities_json TEXT NOT NULL DEFAULT '[]',
                    last_seen_at DATETIME,
                    revoked_at DATETIME,
                    created_at DATETIME NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES user(id)
                )
                """
            )
        )
        db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_local_bridge_user_id ON local_bridge(user_id)"))
        db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_local_bridge_token_hash ON local_bridge(token_hash)"))
        db.session.commit()

    if "local_bridge_command" not in existing_tables:
        db.session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS local_bridge_command (
                    id INTEGER PRIMARY KEY,
                    bridge_id INTEGER NOT NULL,
                    command_type VARCHAR(64) NOT NULL DEFAULT 'invoke',
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    status VARCHAR(32) NOT NULL DEFAULT 'queued',
                    result_json TEXT,
                    error TEXT,
                    created_at DATETIME NOT NULL,
                    claimed_at DATETIME,
                    completed_at DATETIME,
                    FOREIGN KEY(bridge_id) REFERENCES local_bridge(id)
                )
                """
            )
        )
        db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_local_bridge_command_bridge_id ON local_bridge_command(bridge_id)"))
        db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_local_bridge_command_status ON local_bridge_command(status)"))
        db.session.commit()

    if "user_connector_config" not in existing_tables:
        db.session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS user_connector_config (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    key VARCHAR(64) NOT NULL,
                    config_json TEXT NOT NULL DEFAULT '{}',
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES user(id)
                )
                """
            )
        )
        db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_user_connector_config_user_id ON user_connector_config(user_id)"))
        db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_user_connector_config_key ON user_connector_config(key)"))
        db.session.execute(
            text("CREATE UNIQUE INDEX IF NOT EXISTS uq_user_connector_config ON user_connector_config(user_id, key)")
        )
        db.session.commit()


def _migrate_legacy_connector_settings() -> None:
    from .models import User, UserConnectorConfig, utc_now

    users = (
        User.query.filter(User.home_assistant_url.isnot(None))
        .filter(User.home_assistant_token.isnot(None))
        .all()
    )
    changed = False
    for user in users:
        existing = UserConnectorConfig.query.filter_by(user_id=user.id, key="home_assistant").first()
        if existing is not None:
            continue
        config = {
            "base_url": (user.home_assistant_url or "").strip(),
            "token": (user.home_assistant_token or "").strip(),
        }
        if not config["base_url"] or not config["token"]:
            continue
        db.session.add(
            UserConnectorConfig(
                user_id=user.id,
                key="home_assistant",
                config_json=json.dumps(config, ensure_ascii=False),
                created_at=utc_now(),
                updated_at=utc_now(),
            )
        )
        changed = True
    if changed:
        db.session.commit()
