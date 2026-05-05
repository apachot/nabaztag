from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from ..models import ConnectionStatus


class DeviceFamily(str, Enum):
    NABAZTAG_V1 = "nabaztag-v1"
    NABAZTAG_TAG = "nabaztag-tag"
    KAROTZ = "karotz"


class ImplementationStatus(str, Enum):
    IMPLEMENTED = "implemented"
    PLANNED = "planned"


class PrimitiveSupportStatus(str, Enum):
    SUPPORTED = "supported"
    PARTIAL = "partial"
    UNSUPPORTED = "unsupported"
    PLANNED = "planned"
    RESEARCH = "research"


class StandardPrimitive(str, Enum):
    CONNECT = "lifecycle.connect"
    DISCONNECT = "lifecycle.disconnect"
    SYNC = "lifecycle.sync"
    SLEEP = "lifecycle.sleep"
    WAKEUP = "lifecycle.wakeup"
    EARS_MOVE = "ears.move"
    LED_SET = "led.set"
    AUDIO_PLAY = "audio.play"
    AUDIO_RECORDING_START = "audio.recording.start"
    AUDIO_RECORDING_STOP = "audio.recording.stop"
    VIDEO_SNAPSHOT = "video.snapshot"
    VIDEO_STREAM_START = "video.stream.start"
    VIDEO_STREAM_STOP = "video.stream.stop"


class PrimitiveSupportDescriptor(BaseModel):
    primitive: StandardPrimitive
    status: PrimitiveSupportStatus
    summary: str
    limitations: list[str] = Field(default_factory=list)


class DeviceModelDescriptor(BaseModel):
    key: str = Field(min_length=2, max_length=64, pattern=r"^[a-z0-9-]+$")
    family: DeviceFamily
    label: str = Field(min_length=2, max_length=128)
    implementation_status: ImplementationStatus
    transport: str = Field(min_length=2, max_length=128)
    summary: str
    implementation_notes: str | None = None
    documentation_refs: list[str] = Field(default_factory=list)
    surfaces: list[Literal["api", "mcp"]] = Field(default_factory=list)
    primitives: list[PrimitiveSupportDescriptor] = Field(default_factory=list)


class DeviceModelListResponse(BaseModel):
    models: list[DeviceModelDescriptor] = Field(default_factory=list)


class DeviceModelResponse(BaseModel):
    model: DeviceModelDescriptor


class DeviceTarget(BaseModel):
    host: str = Field(min_length=1, max_length=255)
    port: int | None = Field(default=None, ge=1, le=65535)
    label: str | None = Field(default=None, max_length=128)
    username: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, max_length=255)
    use_tls: bool | None = None
    connect_timeout_seconds: float | None = Field(default=None, gt=0, le=30)
    read_timeout_seconds: float | None = Field(default=None, gt=0, le=60)
    metadata: dict[str, str] = Field(default_factory=dict)


class StandardizedDeviceState(BaseModel):
    connection_status: ConnectionStatus | None = None
    left_ear: int | None = Field(default=None, ge=0, le=16)
    right_ear: int | None = Field(default=None, ge=0, le=16)
    led_nose: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    led_left: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    led_center: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    led_right: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    led_bottom: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    audio_playing: bool | None = None
    recording: bool | None = None
    video_streaming: bool | None = None
    last_audio_url: str | None = None
    last_recording_id: str | None = None
    last_snapshot_format: str | None = None


class ConnectPrimitiveRequest(BaseModel):
    primitive: Literal["lifecycle.connect"] = "lifecycle.connect"
    mode: Literal["device", "simulated"] = "device"


class DisconnectPrimitiveRequest(BaseModel):
    primitive: Literal["lifecycle.disconnect"] = "lifecycle.disconnect"


class SyncPrimitiveRequest(BaseModel):
    primitive: Literal["lifecycle.sync"] = "lifecycle.sync"


class SleepPrimitiveRequest(BaseModel):
    primitive: Literal["lifecycle.sleep"] = "lifecycle.sleep"


class WakeupPrimitiveRequest(BaseModel):
    primitive: Literal["lifecycle.wakeup"] = "lifecycle.wakeup"


class MoveEarsPrimitiveRequest(BaseModel):
    primitive: Literal["ears.move"] = "ears.move"
    left: int = Field(ge=0, le=16)
    right: int = Field(ge=0, le=16)


class SetLedPrimitiveRequest(BaseModel):
    primitive: Literal["led.set"] = "led.set"
    target: Literal["nose", "left", "center", "right", "bottom", "all"]
    color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")


class PlayAudioPrimitiveRequest(BaseModel):
    primitive: Literal["audio.play"] = "audio.play"
    url: str = Field(min_length=1)


class StartRecordingPrimitiveRequest(BaseModel):
    primitive: Literal["audio.recording.start"] = "audio.recording.start"
    max_duration_seconds: int = Field(default=10, ge=1, le=120)


class StopRecordingPrimitiveRequest(BaseModel):
    primitive: Literal["audio.recording.stop"] = "audio.recording.stop"
    reason: Literal["user", "timeout"] = "user"


class VideoSnapshotPrimitiveRequest(BaseModel):
    primitive: Literal["video.snapshot"] = "video.snapshot"
    output_format: Literal["jpeg", "png"] = "jpeg"
    max_wait_seconds: float = Field(default=5.0, gt=0, le=30)


class VideoStreamStartPrimitiveRequest(BaseModel):
    primitive: Literal["video.stream.start"] = "video.stream.start"


class VideoStreamStopPrimitiveRequest(BaseModel):
    primitive: Literal["video.stream.stop"] = "video.stream.stop"


StandardizedPrimitiveRequest = Annotated[
    ConnectPrimitiveRequest
    | DisconnectPrimitiveRequest
    | SyncPrimitiveRequest
    | SleepPrimitiveRequest
    | WakeupPrimitiveRequest
    | MoveEarsPrimitiveRequest
    | SetLedPrimitiveRequest
    | PlayAudioPrimitiveRequest
    | StartRecordingPrimitiveRequest
    | StopRecordingPrimitiveRequest
    | VideoSnapshotPrimitiveRequest
    | VideoStreamStartPrimitiveRequest
    | VideoStreamStopPrimitiveRequest,
    Field(discriminator="primitive"),
]


class DeviceProbeRequest(BaseModel):
    model_key: str = Field(min_length=2, max_length=64, pattern=r"^[a-z0-9-]+$")
    target: DeviceTarget


class DeviceProbeResult(BaseModel):
    model_key: str
    adapter: str
    reachable: bool
    message: str
    connection_status: ConnectionStatus | None = None
    transport_state: str | None = None
    raw: dict = Field(default_factory=dict)


class DeviceExecutionRequest(BaseModel):
    model_key: str = Field(min_length=2, max_length=64, pattern=r"^[a-z0-9-]+$")
    target: DeviceTarget
    command: StandardizedPrimitiveRequest


class DeviceExecutionResult(BaseModel):
    ok: bool = True
    model_key: str
    adapter: str
    primitive: str
    message: str
    connection_status: ConnectionStatus | None = None
    state: StandardizedDeviceState = Field(default_factory=StandardizedDeviceState)
    warnings: list[str] = Field(default_factory=list)
    raw: dict = Field(default_factory=dict)
