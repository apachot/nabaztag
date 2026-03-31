from __future__ import annotations

from .types import ProtocolCommandEnvelope
from ..models import AudioCommand, EarsCommand, LedCommand, RecordingStartCommand, RecordingStopCommand


def build_connect_command(mode: str) -> ProtocolCommandEnvelope:
    return ProtocolCommandEnvelope(
        kind="connect",
        payload={"type": "mode", "mode": "interactive" if mode == "device" else "idle"},
    )


def build_disconnect_command() -> ProtocolCommandEnvelope:
    return ProtocolCommandEnvelope(
        kind="disconnect",
        payload={"type": "mode", "mode": "idle", "events": []},
    )


def build_sync_command() -> ProtocolCommandEnvelope:
    return ProtocolCommandEnvelope(
        kind="sync",
        payload={"type": "state"},
    )


def build_sleep_command() -> ProtocolCommandEnvelope:
    return ProtocolCommandEnvelope(
        kind="sleep",
        payload={"type": "sleep"},
    )


def build_wakeup_command() -> ProtocolCommandEnvelope:
    return ProtocolCommandEnvelope(
        kind="wakeup",
        payload={"type": "wakeup"},
    )


def build_led_command(payload: LedCommand) -> ProtocolCommandEnvelope:
    animation_colors = (
        {"left": payload.color, "center": payload.color, "right": payload.color}
        if payload.target == "all"
        else {payload.target: payload.color}
    )
    return ProtocolCommandEnvelope(
        kind="info",
        payload={
            "type": "info",
            "info_id": "control-surface",
            "animation": {
                "tempo": 25,
                "colors": [animation_colors],
            },
        },
    )


def build_ears_command(payload: EarsCommand) -> ProtocolCommandEnvelope:
    return ProtocolCommandEnvelope(
        kind="ears",
        payload={
            "type": "ears",
            "left": payload.left,
            "right": payload.right,
        },
    )


def build_audio_command(payload: AudioCommand) -> ProtocolCommandEnvelope:
    return ProtocolCommandEnvelope(
        kind="command",
        payload={
            "type": "command",
            "sequence": [
                {
                    "audio": [payload.url],
                    "choreography": "urn:x-chor:streaming",
                }
            ],
        },
    )


def build_recording_start_command(payload: RecordingStartCommand) -> ProtocolCommandEnvelope:
    return ProtocolCommandEnvelope(
        kind="start_recording",
        payload={
            "type": "recording_start",
            "max_duration_seconds": payload.max_duration_seconds,
        },
    )


def build_recording_stop_command(payload: RecordingStopCommand) -> ProtocolCommandEnvelope:
    return ProtocolCommandEnvelope(
        kind="stop_recording",
        payload={
            "type": "recording_stop",
            "reason": payload.reason,
        },
    )
