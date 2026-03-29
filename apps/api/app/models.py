from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ConnectionStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    SIMULATED = "simulated"


class CommandType(str, Enum):
    LED = "led"
    EARS = "ears"
    AUDIO = "audio"
    RECORDING_START = "recording_start"
    RECORDING_STOP = "recording_stop"


class CommandStatus(str, Enum):
    QUEUED = "queued"
    APPLIED = "applied"
    FAILED = "failed"


class RabbitState(BaseModel):
    left_ear: int = Field(default=8, ge=0, le=16)
    right_ear: int = Field(default=8, ge=0, le=16)
    led_nose: str = "#ffffff"
    led_left: str = "#ffffff"
    led_center: str = "#ffffff"
    led_right: str = "#ffffff"
    led_bottom: str = "#ffffff"
    audio_playing: bool = False
    recording: bool = False
    last_audio_url: str | None = None
    last_recording_id: str | None = None


class RabbitTarget(BaseModel):
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(default=10543, ge=1, le=65535)


class Rabbit(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    slug: str
    name: str
    connection_status: ConnectionStatus = ConnectionStatus.SIMULATED
    device_serial: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    state: RabbitState = Field(default_factory=RabbitState)
    target: RabbitTarget | None = None


class RabbitCreate(BaseModel):
    slug: str = Field(min_length=2, max_length=32, pattern=r"^[a-z0-9-]+$")
    name: str = Field(min_length=2, max_length=64)


class RabbitSummary(BaseModel):
    id: str
    slug: str
    name: str
    connection_status: ConnectionStatus
    updated_at: datetime


class RabbitSync(BaseModel):
    rabbit: Rabbit
    synced_at: datetime = Field(default_factory=utc_now)


class RabbitTargetUpdate(BaseModel):
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(default=10543, ge=1, le=65535)


class RabbitDeviceLink(BaseModel):
    serial: str = Field(min_length=8, max_length=32)


class Event(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    rabbit_id: str
    type: str
    message: str
    created_at: datetime = Field(default_factory=utc_now)
    payload: dict = Field(default_factory=dict)


class Command(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    rabbit_id: str
    type: CommandType
    status: CommandStatus = CommandStatus.QUEUED
    created_at: datetime = Field(default_factory=utc_now)
    applied_at: datetime | None = None
    payload: dict = Field(default_factory=dict)


class LedCommand(BaseModel):
    target: Literal["nose", "left", "center", "right", "bottom", "all"]
    color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")


class EarsCommand(BaseModel):
    left: int = Field(ge=0, le=16)
    right: int = Field(ge=0, le=16)


class AudioCommand(BaseModel):
    url: str = Field(min_length=1)


class RecordingStartCommand(BaseModel):
    max_duration_seconds: int = Field(default=10, ge=1, le=120)


class RecordingStopCommand(BaseModel):
    reason: Literal["user", "timeout"] = "user"


class ConnectionCommand(BaseModel):
    mode: Literal["simulated", "device"] = "simulated"


class DiscoveryProbeRequest(BaseModel):
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(default=10543, ge=1, le=65535)
    timeout_seconds: float = Field(default=3.0, gt=0, le=30)


class DiscoveryProbeResult(BaseModel):
    reachable: bool
    host: str
    port: int
    state: str | None = None
    connection_status: ConnectionStatus | None = None
    packet: dict = Field(default_factory=dict)
    message: str


class BootstrapConfigRequest(BaseModel):
    rabbit_id: str | None = None
    bootstrap_host: str = Field(default="192.168.0.1", min_length=1, max_length=255)
    bootstrap_port: int = Field(default=80, ge=1, le=65535)
    rabbit_setup_ssid: str = Field(default="NabaztagXX", min_length=1, max_length=64)
    home_wifi_ssid: str = Field(min_length=1, max_length=64)
    home_wifi_password: str = Field(min_length=1, max_length=128)
    server_base_url: str = Field(min_length=1, max_length=255)


class BootstrapConfigResult(BaseModel):
    submitted: bool
    bootstrap_url: str
    violet_platform: str
    message: str
    next_steps: list[str] = Field(default_factory=list)
