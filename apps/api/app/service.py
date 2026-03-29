from __future__ import annotations

from .gateway import RabbitGateway
from .models import (
    AudioCommand,
    Command,
    CommandStatus,
    CommandType,
    ConnectionCommand,
    EarsCommand,
    LedCommand,
    Rabbit,
    RabbitCreate,
    RabbitDeviceLink,
    RabbitSync,
    RabbitTarget,
    RabbitTargetUpdate,
    RecordingStartCommand,
    RecordingStopCommand,
    utc_now,
)
from .store import InMemoryStore


class RabbitService:
    def __init__(self, data_store: InMemoryStore, gateway: RabbitGateway) -> None:
        self.store = data_store
        self.gateway = gateway

    def list_rabbits(self) -> list[Rabbit]:
        return self.store.list_rabbits()

    def create_rabbit(self, payload: RabbitCreate) -> Rabbit:
        rabbit = self.store.create_rabbit(payload)
        self.store.append_event(
            rabbit.id,
            "rabbit.gateway.attached",
            "Rabbit attached to simulated gateway",
            {"gateway": self.gateway.__class__.__name__},
        )
        return rabbit

    def get_rabbit(self, rabbit_id: str) -> Rabbit:
        return self.store.get_rabbit(rabbit_id)

    def list_events(self, rabbit_id: str):
        return self.store.list_events(rabbit_id)

    def list_commands(self, rabbit_id: str):
        return self.store.list_commands(rabbit_id)

    def set_target(self, rabbit_id: str, payload: RabbitTargetUpdate) -> Rabbit:
        rabbit = self.store.get_rabbit(rabbit_id)
        rabbit.target = RabbitTarget(host=payload.host, port=payload.port)
        rabbit.updated_at = utc_now()
        self.store.replace_rabbit(rabbit)
        self.store.append_event(
            rabbit_id,
            "rabbit.target.updated",
            "Rabbit target updated",
            rabbit.target.model_dump(),
        )
        return rabbit

    def link_device(self, rabbit_id: str, payload: RabbitDeviceLink) -> Rabbit:
        rabbit = self.store.get_rabbit(rabbit_id)
        rabbit.device_serial = payload.serial.lower()
        rabbit.connection_status = ConnectionStatus.ONLINE
        rabbit.updated_at = utc_now()
        self.store.replace_rabbit(rabbit)
        self.store.append_event(
            rabbit_id,
            "rabbit.device.linked",
            "Rabbit linked to observed device",
            {"serial": rabbit.device_serial, "connection_status": rabbit.connection_status},
        )
        return rabbit

    def connect(self, rabbit_id: str, payload: ConnectionCommand) -> RabbitSync:
        rabbit = self.store.get_rabbit(rabbit_id)
        sync = self.gateway.connect(rabbit, payload)
        self.store.replace_rabbit(sync.rabbit)
        self.store.append_event(
            rabbit_id,
            "rabbit.connected",
            "Rabbit connected to gateway",
            {"mode": payload.mode, "connection_status": sync.rabbit.connection_status},
        )
        return sync

    def disconnect(self, rabbit_id: str) -> RabbitSync:
        rabbit = self.store.get_rabbit(rabbit_id)
        sync = self.gateway.disconnect(rabbit)
        self.store.replace_rabbit(sync.rabbit)
        self.store.append_event(
            rabbit_id,
            "rabbit.disconnected",
            "Rabbit disconnected from gateway",
            {"connection_status": sync.rabbit.connection_status},
        )
        return sync

    def sync(self, rabbit_id: str) -> RabbitSync:
        rabbit = self.store.get_rabbit(rabbit_id)
        sync = self.gateway.sync(rabbit)
        self.store.replace_rabbit(sync.rabbit)
        self.store.append_event(
            rabbit_id,
            "rabbit.synced",
            "Rabbit state synchronized with gateway",
            {"connection_status": sync.rabbit.connection_status},
        )
        return sync

    def apply_led(self, rabbit_id: str, payload: LedCommand) -> Command:
        rabbit = self.store.get_rabbit(rabbit_id)
        command = self.store.queue_command(rabbit_id, CommandType.LED, payload.model_dump())
        rabbit.state = self.gateway.set_led(rabbit, payload)
        self._mark_applied(rabbit, command)
        self.store.append_event(rabbit_id, "rabbit.led.updated", "LED state updated", payload.model_dump())
        return command

    def apply_ears(self, rabbit_id: str, payload: EarsCommand) -> Command:
        rabbit = self.store.get_rabbit(rabbit_id)
        command = self.store.queue_command(rabbit_id, CommandType.EARS, payload.model_dump())
        rabbit.state = self.gateway.set_ears(rabbit, payload)
        self._mark_applied(rabbit, command)
        self.store.append_event(rabbit_id, "rabbit.ears.updated", "Ear positions updated", payload.model_dump())
        return command

    def start_audio(self, rabbit_id: str, payload: AudioCommand) -> Command:
        rabbit = self.store.get_rabbit(rabbit_id)
        command = self.store.queue_command(rabbit_id, CommandType.AUDIO, payload.model_dump())
        rabbit.state = self.gateway.play_audio(rabbit, payload)
        self._mark_applied(rabbit, command)
        self.store.append_event(rabbit_id, "rabbit.audio.started", "Audio playback started", payload.model_dump())
        return command

    def start_recording(self, rabbit_id: str, payload: RecordingStartCommand) -> Command:
        rabbit = self.store.get_rabbit(rabbit_id)
        command = self.store.queue_command(rabbit_id, CommandType.RECORDING_START, payload.model_dump())
        rabbit.state = self.gateway.start_recording(rabbit, payload)
        self._mark_applied(rabbit, command)
        self.store.append_event(rabbit_id, "rabbit.recording.started", "Recording started", payload.model_dump())
        return command

    def stop_recording(self, rabbit_id: str, payload: RecordingStopCommand) -> Command:
        rabbit = self.store.get_rabbit(rabbit_id)
        command = self.store.queue_command(rabbit_id, CommandType.RECORDING_STOP, payload.model_dump())
        rabbit.state = self.gateway.stop_recording(rabbit, payload)
        self._mark_applied(rabbit, command)
        self.store.append_event(
            rabbit_id,
            "rabbit.recording.stopped",
            "Recording stopped",
            {**payload.model_dump(), "recording_id": rabbit.state.last_recording_id},
        )
        return command

    def _mark_applied(self, rabbit: Rabbit, command: Command) -> None:
        rabbit.updated_at = utc_now()
        command.status = CommandStatus.APPLIED
        command.applied_at = utc_now()
