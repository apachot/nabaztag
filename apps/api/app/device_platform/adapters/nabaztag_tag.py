from __future__ import annotations

from ..models import (
    DeviceExecutionResult,
    DeviceFamily,
    DeviceModelDescriptor,
    DeviceProbeResult,
    DeviceTarget,
    ImplementationStatus,
    PrimitiveSupportDescriptor,
    PrimitiveSupportStatus,
    SetLedPrimitiveRequest,
    StandardPrimitive,
    StandardizedDeviceState,
    StandardizedPrimitiveRequest,
)
from ...models import AudioCommand, ConnectionStatus, EarsCommand, LedCommand
from ...protocol.client import ProtocolClient
from ...protocol.commands import (
    build_audio_command,
    build_connect_command,
    build_disconnect_command,
    build_ears_command,
    build_led_command,
    build_sleep_command,
    build_sync_command,
    build_wakeup_command,
)
from ...settings import GatewaySettings
from ..errors import UnsupportedPrimitiveError

from .base import DeviceAdapter


NABAZTAG_TAG_DESCRIPTOR = DeviceModelDescriptor(
    key="nabaztag-tag",
    family=DeviceFamily.NABAZTAG_TAG,
    label="Nabaztag:tag",
    implementation_status=ImplementationStatus.IMPLEMENTED,
    transport="nabd JSONL over TCP",
    summary=(
        "First concrete device adapter. It exposes the standardized primitive layer on top "
        "of the existing nabd TCP protocol used by Nabaztag:tag devices."
    ),
    implementation_notes=(
        "This first adapter is intentionally conservative: it only exposes primitives already "
        "mapped cleanly to the documented nabd transport."
    ),
    documentation_refs=[
        "docs/device-platform-architecture.md",
        "docs/protocol-notes.md",
        "docs/nabd-gap-analysis.md",
        "docs/hardware-recon.md",
    ],
    surfaces=["api", "mcp"],
    primitives=[
        PrimitiveSupportDescriptor(
            primitive=StandardPrimitive.CONNECT,
            status=PrimitiveSupportStatus.SUPPORTED,
            summary="Switch the rabbit to interactive or simulated mode through nabd.",
        ),
        PrimitiveSupportDescriptor(
            primitive=StandardPrimitive.DISCONNECT,
            status=PrimitiveSupportStatus.SUPPORTED,
            summary="Return the rabbit to idle mode and mark it offline in the abstraction layer.",
        ),
        PrimitiveSupportDescriptor(
            primitive=StandardPrimitive.SYNC,
            status=PrimitiveSupportStatus.SUPPORTED,
            summary="Read the initial nabd state packet and normalize it.",
        ),
        PrimitiveSupportDescriptor(
            primitive=StandardPrimitive.SLEEP,
            status=PrimitiveSupportStatus.SUPPORTED,
            summary="Send the documented sleep packet through nabd.",
        ),
        PrimitiveSupportDescriptor(
            primitive=StandardPrimitive.WAKEUP,
            status=PrimitiveSupportStatus.SUPPORTED,
            summary="Send the documented wakeup packet through nabd.",
        ),
        PrimitiveSupportDescriptor(
            primitive=StandardPrimitive.EARS_MOVE,
            status=PrimitiveSupportStatus.SUPPORTED,
            summary="Move both ears through the native nabd ears packet.",
        ),
        PrimitiveSupportDescriptor(
            primitive=StandardPrimitive.LED_SET,
            status=PrimitiveSupportStatus.PARTIAL,
            summary="Map LED control to nabd idle animation packets.",
            limitations=[
                "Only left, center and right idle LEDs are supported by this adapter.",
                "nose and bottom LEDs are intentionally rejected until a lower-level transport is added.",
            ],
        ),
        PrimitiveSupportDescriptor(
            primitive=StandardPrimitive.AUDIO_PLAY,
            status=PrimitiveSupportStatus.SUPPORTED,
            summary="Play audio URLs through the documented nabd command sequence.",
        ),
        PrimitiveSupportDescriptor(
            primitive=StandardPrimitive.AUDIO_RECORDING_START,
            status=PrimitiveSupportStatus.UNSUPPORTED,
            summary="nabd does not document raw recording retrieval for this adapter.",
        ),
        PrimitiveSupportDescriptor(
            primitive=StandardPrimitive.AUDIO_RECORDING_STOP,
            status=PrimitiveSupportStatus.UNSUPPORTED,
            summary="nabd does not document raw recording retrieval for this adapter.",
        ),
        PrimitiveSupportDescriptor(
            primitive=StandardPrimitive.VIDEO_SNAPSHOT,
            status=PrimitiveSupportStatus.UNSUPPORTED,
            summary="Nabaztag:tag does not expose any video primitive.",
        ),
        PrimitiveSupportDescriptor(
            primitive=StandardPrimitive.VIDEO_STREAM_START,
            status=PrimitiveSupportStatus.UNSUPPORTED,
            summary="Nabaztag:tag does not expose any video primitive.",
        ),
        PrimitiveSupportDescriptor(
            primitive=StandardPrimitive.VIDEO_STREAM_STOP,
            status=PrimitiveSupportStatus.UNSUPPORTED,
            summary="Nabaztag:tag does not expose any video primitive.",
        ),
    ],
)


class NabaztagTagAdapter(DeviceAdapter):
    def __init__(self, defaults: GatewaySettings) -> None:
        self.defaults = defaults

    @property
    def model_key(self) -> str:
        return NABAZTAG_TAG_DESCRIPTOR.key

    def descriptor(self) -> DeviceModelDescriptor:
        return NABAZTAG_TAG_DESCRIPTOR.model_copy(deep=True)

    def probe(self, target: DeviceTarget) -> DeviceProbeResult:
        client = ProtocolClient(self._settings_for(target))
        target_port = self._target_port(target)
        probe_result = client.probe(
            host=target.host,
            port=target_port,
            timeout_seconds=target.connect_timeout_seconds or self.defaults.connect_timeout_seconds,
        )
        return DeviceProbeResult(
            model_key=self.model_key,
            adapter=self.__class__.__name__,
            reachable=probe_result.reachable,
            message=probe_result.message,
            connection_status=probe_result.connection_status,
            transport_state=probe_result.state,
            raw={
                "host": probe_result.host,
                "port": probe_result.port,
                "packet": probe_result.packet,
            },
        )

    def execute(
        self,
        target: DeviceTarget,
        command: StandardizedPrimitiveRequest,
    ) -> DeviceExecutionResult:
        client = ProtocolClient(self._settings_for(target))
        target_port = self._target_port(target)
        rabbit_slug = target.label or target.metadata.get("rabbit_slug") or target.host.replace(".", "-")

        primitive = getattr(command, "primitive")
        if primitive == StandardPrimitive.CONNECT.value:
            event = client.send_to(
                rabbit_slug=rabbit_slug,
                command=build_connect_command(command.mode),
                host=target.host,
                port=target_port,
            )
            return self._result(
                primitive=primitive,
                message=f"Nabaztag:tag connected in {command.mode} mode.",
                connection_status=event.connection_status,
                state=StandardizedDeviceState(connection_status=event.connection_status),
                raw=event.payload,
            )

        if primitive == StandardPrimitive.DISCONNECT.value:
            event = client.send_to(
                rabbit_slug=rabbit_slug,
                command=build_disconnect_command(),
                host=target.host,
                port=target_port,
            )
            return self._result(
                primitive=primitive,
                message="Nabaztag:tag returned to idle mode.",
                connection_status=ConnectionStatus.OFFLINE,
                state=StandardizedDeviceState(connection_status=ConnectionStatus.OFFLINE, audio_playing=False),
                raw=event.payload,
            )

        if primitive == StandardPrimitive.SYNC.value:
            event = client.send_to(
                rabbit_slug=rabbit_slug,
                command=build_sync_command(),
                host=target.host,
                port=target_port,
            )
            return self._result(
                primitive=primitive,
                message="Nabaztag:tag state synchronized through nabd.",
                connection_status=event.connection_status,
                state=StandardizedDeviceState(connection_status=event.connection_status),
                raw=event.payload,
            )

        if primitive == StandardPrimitive.SLEEP.value:
            event = client.send_to(
                rabbit_slug=rabbit_slug,
                command=build_sleep_command(),
                host=target.host,
                port=target_port,
            )
            return self._result(
                primitive=primitive,
                message="Sleep packet sent to Nabaztag:tag.",
                connection_status=event.connection_status,
                state=StandardizedDeviceState(connection_status=event.connection_status, audio_playing=False),
                raw=event.payload,
            )

        if primitive == StandardPrimitive.WAKEUP.value:
            event = client.send_to(
                rabbit_slug=rabbit_slug,
                command=build_wakeup_command(),
                host=target.host,
                port=target_port,
            )
            return self._result(
                primitive=primitive,
                message="Wakeup packet sent to Nabaztag:tag.",
                connection_status=event.connection_status,
                state=StandardizedDeviceState(connection_status=event.connection_status),
                raw=event.payload,
            )

        if primitive == StandardPrimitive.EARS_MOVE.value:
            event = client.send_to(
                rabbit_slug=rabbit_slug,
                command=build_ears_command(EarsCommand(left=command.left, right=command.right)),
                host=target.host,
                port=target_port,
            )
            return self._result(
                primitive=primitive,
                message="Ear positions updated on Nabaztag:tag.",
                connection_status=event.connection_status,
                state=StandardizedDeviceState(
                    connection_status=event.connection_status,
                    left_ear=command.left,
                    right_ear=command.right,
                ),
                raw=event.payload,
            )

        if primitive == StandardPrimitive.LED_SET.value:
            return self._execute_led(
                client=client,
                rabbit_slug=rabbit_slug,
                target=target,
                command=command,
            )

        if primitive == StandardPrimitive.AUDIO_PLAY.value:
            event = client.send_to(
                rabbit_slug=rabbit_slug,
                command=build_audio_command(AudioCommand(url=command.url)),
                host=target.host,
                port=target_port,
            )
            return self._result(
                primitive=primitive,
                message="Audio playback requested on Nabaztag:tag.",
                connection_status=event.connection_status,
                state=StandardizedDeviceState(
                    connection_status=event.connection_status,
                    audio_playing=True,
                    last_audio_url=command.url,
                ),
                raw=event.payload,
            )

        if primitive in {
            StandardPrimitive.AUDIO_RECORDING_START.value,
            StandardPrimitive.AUDIO_RECORDING_STOP.value,
        }:
            raise UnsupportedPrimitiveError(
                "Nabaztag:tag recording is intentionally outside the first adapter because the current "
                "nabd transport does not document raw audio capture retrieval."
            )

        if primitive in {
            StandardPrimitive.VIDEO_SNAPSHOT.value,
            StandardPrimitive.VIDEO_STREAM_START.value,
            StandardPrimitive.VIDEO_STREAM_STOP.value,
        }:
            raise UnsupportedPrimitiveError("Nabaztag:tag does not expose any video capture primitive.")

        raise UnsupportedPrimitiveError(f"Unsupported standardized primitive for Nabaztag:tag: {primitive}")

    def _execute_led(
        self,
        *,
        client: ProtocolClient,
        rabbit_slug: str,
        target: DeviceTarget,
        command: SetLedPrimitiveRequest,
    ) -> DeviceExecutionResult:
        if command.target in {"nose", "bottom"}:
            raise UnsupportedPrimitiveError(
                "This Nabaztag:tag adapter only supports left/center/right idle LEDs through nabd. "
                f"`{command.target}` requires a lower-level adapter."
            )

        target_port = self._target_port(target)
        event = client.send_to(
            rabbit_slug=rabbit_slug,
            command=build_led_command(LedCommand(target=command.target, color=command.color)),
            host=target.host,
            port=target_port,
        )
        state = StandardizedDeviceState(connection_status=event.connection_status)
        warnings: list[str] = []
        targets = ["left", "center", "right"] if command.target == "all" else [command.target]
        if command.target == "all":
            warnings.append("`all` only updates left/center/right on Nabaztag:tag through nabd.")
        for led_target in targets:
            setattr(state, f"led_{led_target}", command.color)
        return self._result(
            primitive=command.primitive,
            message="LED state updated on Nabaztag:tag.",
            connection_status=event.connection_status,
            state=state,
            warnings=warnings,
            raw=event.payload,
        )

    def _result(
        self,
        *,
        primitive: str,
        message: str,
        connection_status: ConnectionStatus | None = None,
        state: StandardizedDeviceState | None = None,
        warnings: list[str] | None = None,
        raw: dict | None = None,
    ) -> DeviceExecutionResult:
        return DeviceExecutionResult(
            model_key=self.model_key,
            adapter=self.__class__.__name__,
            primitive=primitive,
            message=message,
            connection_status=connection_status,
            state=state or StandardizedDeviceState(),
            warnings=warnings or [],
            raw=raw or {},
        )

    def _settings_for(self, target: DeviceTarget) -> GatewaySettings:
        return GatewaySettings(
            driver="protocol",
            host=target.host,
            port=self._target_port(target),
            username=target.username if target.username is not None else self.defaults.username,
            password=target.password if target.password is not None else self.defaults.password,
            use_tls=target.use_tls if target.use_tls is not None else self.defaults.use_tls,
            connect_timeout_seconds=target.connect_timeout_seconds or self.defaults.connect_timeout_seconds,
            read_timeout_seconds=target.read_timeout_seconds or self.defaults.read_timeout_seconds,
        )

    def _target_port(self, target: DeviceTarget) -> int:
        return target.port or self.defaults.port
