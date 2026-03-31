from __future__ import annotations

from abc import ABC, abstractmethod

from .protocol.client import ProtocolClient
from .protocol.commands import (
    build_audio_command,
    build_connect_command,
    build_disconnect_command,
    build_ears_command,
    build_led_command,
    build_recording_start_command,
    build_recording_stop_command,
    build_sleep_command,
    build_sync_command,
    build_wakeup_command,
)
from .protocol.events import offline_sync, sync_from_event
from .models import (
    AudioCommand,
    ConnectionCommand,
    ConnectionStatus,
    EarsCommand,
    LedCommand,
    Rabbit,
    RabbitState,
    RabbitSync,
    RecordingStartCommand,
    RecordingStopCommand,
    utc_now,
)
from .settings import GatewayError, GatewaySettings


class RabbitGateway(ABC):
    @abstractmethod
    def connect(self, rabbit: Rabbit, payload: ConnectionCommand) -> RabbitSync:
        raise NotImplementedError

    @abstractmethod
    def disconnect(self, rabbit: Rabbit) -> RabbitSync:
        raise NotImplementedError

    @abstractmethod
    def sync(self, rabbit: Rabbit) -> RabbitSync:
        raise NotImplementedError

    @abstractmethod
    def sleep(self, rabbit: Rabbit) -> RabbitSync:
        raise NotImplementedError

    @abstractmethod
    def wakeup(self, rabbit: Rabbit) -> RabbitSync:
        raise NotImplementedError

    @abstractmethod
    def set_led(self, rabbit: Rabbit, payload: LedCommand) -> RabbitState:
        raise NotImplementedError

    @abstractmethod
    def set_ears(self, rabbit: Rabbit, payload: EarsCommand) -> RabbitState:
        raise NotImplementedError

    @abstractmethod
    def play_audio(self, rabbit: Rabbit, payload: AudioCommand) -> RabbitState:
        raise NotImplementedError

    @abstractmethod
    def start_recording(self, rabbit: Rabbit, payload: RecordingStartCommand) -> RabbitState:
        raise NotImplementedError

    @abstractmethod
    def stop_recording(self, rabbit: Rabbit, payload: RecordingStopCommand) -> RabbitState:
        raise NotImplementedError


class SimulatedRabbitGateway(RabbitGateway):
    def connect(self, rabbit: Rabbit, payload: ConnectionCommand) -> RabbitSync:
        rabbit.connection_status = (
            ConnectionStatus.SIMULATED if payload.mode == "simulated" else ConnectionStatus.ONLINE
        )
        rabbit.updated_at = utc_now()
        return RabbitSync(rabbit=rabbit.model_copy(deep=True))

    def disconnect(self, rabbit: Rabbit) -> RabbitSync:
        rabbit.connection_status = ConnectionStatus.OFFLINE
        rabbit.updated_at = utc_now()
        return RabbitSync(rabbit=rabbit.model_copy(deep=True))

    def sync(self, rabbit: Rabbit) -> RabbitSync:
        rabbit.updated_at = utc_now()
        return RabbitSync(rabbit=rabbit.model_copy(deep=True))

    def sleep(self, rabbit: Rabbit) -> RabbitSync:
        rabbit.updated_at = utc_now()
        rabbit.state.audio_playing = False
        return RabbitSync(rabbit=rabbit.model_copy(deep=True))

    def wakeup(self, rabbit: Rabbit) -> RabbitSync:
        rabbit.updated_at = utc_now()
        return RabbitSync(rabbit=rabbit.model_copy(deep=True))

    def set_led(self, rabbit: Rabbit, payload: LedCommand) -> RabbitState:
        state = rabbit.state.model_copy(deep=True)
        targets = ["nose", "left", "center", "right", "bottom"] if payload.target == "all" else [payload.target]
        for target in targets:
            setattr(state, f"led_{target}", payload.color)
        return state

    def set_ears(self, rabbit: Rabbit, payload: EarsCommand) -> RabbitState:
        state = rabbit.state.model_copy(deep=True)
        state.left_ear = payload.left
        state.right_ear = payload.right
        return state

    def play_audio(self, rabbit: Rabbit, payload: AudioCommand) -> RabbitState:
        state = rabbit.state.model_copy(deep=True)
        state.audio_playing = True
        state.last_audio_url = payload.url
        return state

    def start_recording(self, rabbit: Rabbit, payload: RecordingStartCommand) -> RabbitState:
        state = rabbit.state.model_copy(deep=True)
        state.recording = True
        state.last_recording_id = f"rec-{int(utc_now().timestamp())}"
        return state

    def stop_recording(self, rabbit: Rabbit, payload: RecordingStopCommand) -> RabbitState:
        state = rabbit.state.model_copy(deep=True)
        state.recording = False
        state.audio_playing = False
        return state


class NabaztagProtocolGateway(RabbitGateway):
    def __init__(self, settings: GatewaySettings) -> None:
        self.settings = settings
        self.client = ProtocolClient(settings)

    def connect(self, rabbit: Rabbit, payload: ConnectionCommand) -> RabbitSync:
        event = self.client.send_to(
            rabbit_slug=rabbit.slug,
            command=build_connect_command(payload.mode),
            host=self._target_host(rabbit),
            port=self._target_port(rabbit),
        )
        sync = sync_from_event(rabbit, event)
        if payload.mode == "simulated":
            sync.rabbit.connection_status = ConnectionStatus.SIMULATED
        return sync

    def disconnect(self, rabbit: Rabbit) -> RabbitSync:
        event = self.client.send_to(
            rabbit_slug=rabbit.slug,
            command=build_disconnect_command(),
            host=self._target_host(rabbit),
            port=self._target_port(rabbit),
        )
        return sync_from_event(rabbit, event)

    def sync(self, rabbit: Rabbit) -> RabbitSync:
        event = self.client.send_to(
            rabbit_slug=rabbit.slug,
            command=build_sync_command(),
            host=self._target_host(rabbit),
            port=self._target_port(rabbit),
        )
        if event.connection_status is None and not event.state_delta and rabbit.connection_status == ConnectionStatus.OFFLINE:
            return offline_sync(rabbit)
        return sync_from_event(rabbit, event)

    def sleep(self, rabbit: Rabbit) -> RabbitSync:
        event = self.client.send_to(
            rabbit_slug=rabbit.slug,
            command=build_sleep_command(),
            host=self._target_host(rabbit),
            port=self._target_port(rabbit),
        )
        sync = sync_from_event(rabbit, event)
        sync.rabbit.state.audio_playing = False
        return sync

    def wakeup(self, rabbit: Rabbit) -> RabbitSync:
        event = self.client.send_to(
            rabbit_slug=rabbit.slug,
            command=build_wakeup_command(),
            host=self._target_host(rabbit),
            port=self._target_port(rabbit),
        )
        return sync_from_event(rabbit, event)

    def set_led(self, rabbit: Rabbit, payload: LedCommand) -> RabbitState:
        if payload.target in {"nose", "bottom"}:
            raise GatewayError(
                "nabd protocol documents idle LED control for `left`, `center`, `right` only; "
                f"`{payload.target}` is not supported yet in protocol mode"
            )
        self.client.send_to(
            rabbit_slug=rabbit.slug,
            command=build_led_command(payload),
            host=self._target_host(rabbit),
            port=self._target_port(rabbit),
        )
        state = rabbit.state.model_copy(deep=True)
        targets = ["left", "center", "right"] if payload.target == "all" else [payload.target]
        for target in targets:
            if hasattr(state, f"led_{target}"):
                setattr(state, f"led_{target}", payload.color)
        return state

    def set_ears(self, rabbit: Rabbit, payload: EarsCommand) -> RabbitState:
        self.client.send_to(
            rabbit_slug=rabbit.slug,
            command=build_ears_command(payload),
            host=self._target_host(rabbit),
            port=self._target_port(rabbit),
        )
        state = rabbit.state.model_copy(deep=True)
        state.left_ear = payload.left
        state.right_ear = payload.right
        return state

    def play_audio(self, rabbit: Rabbit, payload: AudioCommand) -> RabbitState:
        self.client.send_to(
            rabbit_slug=rabbit.slug,
            command=build_audio_command(payload),
            host=self._target_host(rabbit),
            port=self._target_port(rabbit),
        )
        state = rabbit.state.model_copy(deep=True)
        state.audio_playing = True
        state.last_audio_url = payload.url
        return state

    def start_recording(self, rabbit: Rabbit, payload: RecordingStartCommand) -> RabbitState:
        raise GatewayError(
            "nabd protocol exposes ASR events but does not document raw recording start/stop "
            "with audio file retrieval"
        )

    def stop_recording(self, rabbit: Rabbit, payload: RecordingStopCommand) -> RabbitState:
        raise GatewayError(
            "nabd protocol exposes ASR events but does not document raw recording start/stop "
            "with audio file retrieval"
        )

    def _not_implemented_message(self, operation: str) -> str:
        endpoint = f"{self.settings.host}:{self.settings.port}"
        return (
            f"Nabaztag protocol gateway is configured but `{operation}` is not implemented yet "
            f"for endpoint {endpoint}"
        )

    def _target_host(self, rabbit: Rabbit) -> str:
        if rabbit.target is None:
            raise GatewayError("No target configured for this rabbit. Use the connection assistant first.")
        return rabbit.target.host

    def _target_port(self, rabbit: Rabbit) -> int:
        if rabbit.target is None:
            raise GatewayError("No target configured for this rabbit. Use the connection assistant first.")
        return rabbit.target.port
