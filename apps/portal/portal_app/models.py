from __future__ import annotations

import json
from datetime import datetime, timezone

from flask_login import UserMixin
from sqlalchemy import UniqueConstraint
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db, login_manager


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    openai_api_key = db.Column(db.Text)
    mistral_api_key = db.Column(db.Text)
    home_assistant_url = db.Column(db.Text)
    home_assistant_token = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)

    rabbits = db.relationship("Rabbit", back_populates="owner", cascade="all, delete-orphan")
    mobile_pairing_sessions = db.relationship(
        "MobileAppPairingSession",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    mobile_api_tokens = db.relationship(
        "MobileApiToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    local_bridge_pairing_sessions = db.relationship(
        "LocalBridgePairingSession",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    local_bridges = db.relationship(
        "LocalBridge",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    connector_configs = db.relationship(
        "UserConnectorConfig",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Rabbit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(64), nullable=False)
    personality_prompt = db.Column(db.Text)
    llm_model = db.Column(db.String(64), default="mistral-small-2603")
    tts_voice = db.Column(db.String(64), default="e0580ce5-e63c-4cbe-88c8-a983b80c5f1f")
    auto_performance_enabled = db.Column(db.Boolean, default=False, nullable=False)
    birth_audio_played = db.Column(db.Boolean, default=False, nullable=False)
    auto_performance_frequency_minutes = db.Column(db.Integer, default=180, nullable=False)
    auto_performance_window_start = db.Column(db.String(5), default="09:00")
    auto_performance_window_end = db.Column(db.String(5), default="21:00")
    auto_performance_next_at = db.Column(db.DateTime(timezone=True))
    conversation_summary = db.Column(db.Text)
    conversation_summary_turn_id = db.Column(db.Integer)
    alerts_last_seen_event_id = db.Column(db.Integer)
    connection_status = db.Column(db.String(32), default="offline", nullable=False)
    remote_rabbit_id = db.Column(db.String(64), unique=True, index=True)
    target_host = db.Column(db.String(255))
    target_port = db.Column(db.Integer, default=10543)
    notes = db.Column(db.Text)
    photo_filename = db.Column(db.String(255))
    photo_original_name = db.Column(db.String(255))
    provisioning_state = db.Column(db.String(32), default="draft", nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    owner = db.relationship("User", back_populates="rabbits")
    provisioning_sessions = db.relationship(
        "ProvisioningSession",
        back_populates="rabbit",
        cascade="all, delete-orphan",
    )
    app_pairing_sessions = db.relationship(
        "RabbitAppPairingSession",
        back_populates="rabbit",
        cascade="all, delete-orphan",
    )
    device_observations = db.relationship(
        "DeviceObservation",
        back_populates="rabbit",
        cascade="save-update, merge",
    )
    event_logs = db.relationship(
        "RabbitEventLog",
        back_populates="rabbit",
        cascade="all, delete-orphan",
        order_by="desc(RabbitEventLog.created_at)",
    )
    ztamps = db.relationship(
        "Ztamp",
        back_populates="rabbit",
        cascade="all, delete-orphan",
        order_by="desc(Ztamp.updated_at)",
    )
    conversation_turns = db.relationship(
        "RabbitConversationTurn",
        back_populates="rabbit",
        cascade="all, delete-orphan",
        order_by="RabbitConversationTurn.created_at.asc()",
    )
    precomputed_performances = db.relationship(
        "RabbitPrecomputedPerformance",
        back_populates="rabbit",
        cascade="all, delete-orphan",
        order_by="RabbitPrecomputedPerformance.created_at.asc()",
    )


class RabbitFriendship(db.Model):
    __table_args__ = (
        UniqueConstraint("rabbit_low_id", "rabbit_high_id", name="uq_rabbit_friendship_pair"),
    )

    id = db.Column(db.Integer, primary_key=True)
    rabbit_low_id = db.Column(db.Integer, db.ForeignKey("rabbit.id"), nullable=False, index=True)
    rabbit_high_id = db.Column(db.Integer, db.ForeignKey("rabbit.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)


class DeviceObservation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    serial = db.Column(db.String(32), unique=True, nullable=False, index=True)
    last_seen_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    last_ip = db.Column(db.String(64))
    last_user_agent = db.Column(db.String(255))
    last_path = db.Column(db.String(255))
    firmware = db.Column(db.String(64))
    hardware = db.Column(db.String(32))
    last_query = db.Column(db.Text)
    rabbit_id = db.Column(db.Integer, db.ForeignKey("rabbit.id"), index=True)

    rabbit = db.relationship("Rabbit", back_populates="device_observations")


class ProvisioningSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    rabbit_id = db.Column(db.Integer, db.ForeignKey("rabbit.id"), nullable=False, index=True)
    setup_ssid = db.Column(db.String(64))
    home_wifi_ssid = db.Column(db.String(64))
    server_base_url = db.Column(db.String(255))
    status = db.Column(db.String(32), default="draft", nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)

    rabbit = db.relationship("Rabbit", back_populates="provisioning_sessions")


class RabbitAppPairingSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    rabbit_id = db.Column(db.Integer, db.ForeignKey("rabbit.id"), nullable=False, index=True)
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    status = db.Column(db.String(32), default="pending", nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    consumed_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)

    rabbit = db.relationship("Rabbit", back_populates="app_pairing_sessions")


class MobileAppPairingSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    token = db.Column(db.String(128), unique=True, nullable=False, index=True)
    status = db.Column(db.String(32), default="pending", nullable=False)
    device_name = db.Column(db.String(255))
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    consumed_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)

    user = db.relationship("User", back_populates="mobile_pairing_sessions")


class MobileApiToken(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    label = db.Column(db.String(255))
    token_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    last_used_at = db.Column(db.DateTime(timezone=True))
    revoked_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)

    user = db.relationship("User", back_populates="mobile_api_tokens")


class LocalBridgePairingSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    token = db.Column(db.String(128), unique=True, nullable=False, index=True)
    status = db.Column(db.String(32), default="pending", nullable=False)
    bridge_name = db.Column(db.String(255))
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    consumed_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)

    user = db.relationship("User", back_populates="local_bridge_pairing_sessions")


class LocalBridge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    token_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    capabilities_json = db.Column(db.Text, nullable=False, default="[]")
    last_seen_at = db.Column(db.DateTime(timezone=True))
    revoked_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)

    user = db.relationship("User", back_populates="local_bridges")
    commands = db.relationship(
        "LocalBridgeCommand",
        back_populates="bridge",
        cascade="all, delete-orphan",
        order_by="LocalBridgeCommand.created_at.asc()",
    )

    def capabilities(self) -> list[dict]:
        try:
            value = json.loads(self.capabilities_json or "[]")
        except Exception:
            value = []
        return value if isinstance(value, list) else []

    def set_capabilities(self, capabilities: list[dict]) -> None:
        self.capabilities_json = json.dumps(capabilities, ensure_ascii=False)


class LocalBridgeCommand(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bridge_id = db.Column(db.Integer, db.ForeignKey("local_bridge.id"), nullable=False, index=True)
    command_type = db.Column(db.String(64), nullable=False, default="invoke", index=True)
    payload_json = db.Column(db.Text, nullable=False, default="{}")
    status = db.Column(db.String(32), nullable=False, default="queued", index=True)
    result_json = db.Column(db.Text)
    error = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    claimed_at = db.Column(db.DateTime(timezone=True))
    completed_at = db.Column(db.DateTime(timezone=True))

    bridge = db.relationship("LocalBridge", back_populates="commands")

    def payload_dict(self) -> dict:
        try:
            value = json.loads(self.payload_json or "{}")
        except Exception:
            value = {}
        return value if isinstance(value, dict) else {}

    def set_payload(self, payload: dict) -> None:
        self.payload_json = json.dumps(payload, ensure_ascii=False)

    def result_dict(self) -> dict:
        try:
            value = json.loads(self.result_json or "{}")
        except Exception:
            value = {}
        return value if isinstance(value, dict) else {}

    def set_result(self, result: dict) -> None:
        self.result_json = json.dumps(result, ensure_ascii=False)


class UserConnectorConfig(db.Model):
    __table_args__ = (UniqueConstraint("user_id", "key", name="uq_user_connector_config"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    key = db.Column(db.String(64), nullable=False, index=True)
    config_json = db.Column(db.Text, nullable=False, default="{}")
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    user = db.relationship("User", back_populates="connector_configs")

    def config_dict(self) -> dict:
        try:
            value = json.loads(self.config_json or "{}")
        except Exception:
            value = {}
        return value if isinstance(value, dict) else {}

    def set_config(self, config: dict) -> None:
        self.config_json = json.dumps(config, ensure_ascii=False)


class RabbitEventLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    rabbit_id = db.Column(db.Integer, db.ForeignKey("rabbit.id"), nullable=False, index=True)
    level = db.Column(db.String(16), default="info", nullable=False)
    source = db.Column(db.String(64), nullable=False)
    event_type = db.Column(db.String(120), nullable=False)
    payload = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)

    rabbit = db.relationship("Rabbit", back_populates="event_logs")


class RabbitDeviceCommand(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    rabbit_id = db.Column(db.Integer, db.ForeignKey("rabbit.id"), nullable=False, index=True)
    serial = db.Column(db.String(32), nullable=False, index=True)
    command_type = db.Column(db.String(64), nullable=False, index=True)
    payload = db.Column(db.Text)
    status = db.Column(db.String(32), default="queued", nullable=False, index=True)
    error = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    sent_at = db.Column(db.DateTime(timezone=True))


class RabbitRecording(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    rabbit_id = db.Column(db.Integer, db.ForeignKey("rabbit.id"), nullable=False, index=True)
    serial = db.Column(db.String(32), nullable=False, index=True)
    content_sha1 = db.Column(db.String(40), index=True)
    filename = db.Column(db.String(255), nullable=False, unique=True)
    source_path = db.Column(db.String(255), nullable=False)
    mode = db.Column(db.String(32))
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)


class RabbitConversationTurn(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    rabbit_id = db.Column(db.Integer, db.ForeignKey("rabbit.id"), nullable=False, index=True)
    role = db.Column(db.String(16), nullable=False, index=True)
    text = db.Column(db.Text, nullable=False)
    source = db.Column(db.String(32), nullable=False, default="portal")
    recording_id = db.Column(db.Integer, db.ForeignKey("rabbit_recording.id"), index=True)
    payload = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)

    rabbit = db.relationship("Rabbit", back_populates="conversation_turns")


class RabbitPrecomputedPerformance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    rabbit_id = db.Column(db.Integer, db.ForeignKey("rabbit.id"), nullable=False, index=True)
    text = db.Column(db.Text, nullable=False)
    payload = db.Column(db.Text, nullable=False)
    asset_name = db.Column(db.String(255), nullable=False)
    used_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)

    rabbit = db.relationship("Rabbit", back_populates="precomputed_performances")


class Ztamp(db.Model):
    __table_args__ = (UniqueConstraint("rabbit_id", "tag", name="uq_ztamp_rabbit_tag"),)

    id = db.Column(db.Integer, primary_key=True)
    rabbit_id = db.Column(db.Integer, db.ForeignKey("rabbit.id"), nullable=False, index=True)
    tag = db.Column(db.String(255), nullable=False, index=True)
    name = db.Column(db.String(255))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
    last_seen_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)

    rabbit = db.relationship("Rabbit", back_populates="ztamps")


@login_manager.user_loader
def load_user(user_id: str) -> User | None:
    if not user_id.isdigit():
        return None
    return db.session.get(User, int(user_id))
