from __future__ import annotations

from dataclasses import dataclass

from ..settings import GatewaySettings
from .adapters.base import DeviceAdapter
from .adapters.nabaztag_tag import NabaztagTagAdapter
from .errors import AdapterNotAvailableError, UnknownDeviceModelError
from .models import (
    DeviceFamily,
    DeviceModelDescriptor,
    ImplementationStatus,
    PrimitiveSupportDescriptor,
    PrimitiveSupportStatus,
    StandardPrimitive,
)


@dataclass(frozen=True)
class DeviceCatalogEntry:
    descriptor: DeviceModelDescriptor
    adapter: DeviceAdapter | None = None


class DeviceAdapterCatalog:
    def __init__(self, entries: list[DeviceCatalogEntry]) -> None:
        self._entries = {entry.descriptor.key: entry for entry in entries}

    def list_models(self) -> list[DeviceModelDescriptor]:
        return [entry.descriptor.model_copy(deep=True) for entry in self._sorted_entries()]

    def get_descriptor(self, model_key: str) -> DeviceModelDescriptor:
        entry = self._entries.get(model_key)
        if entry is None:
            raise UnknownDeviceModelError(f"Unknown device model `{model_key}`")
        return entry.descriptor.model_copy(deep=True)

    def get_adapter(self, model_key: str) -> DeviceAdapter:
        entry = self._entries.get(model_key)
        if entry is None:
            raise UnknownDeviceModelError(f"Unknown device model `{model_key}`")
        if entry.adapter is None:
            raise AdapterNotAvailableError(
                f"Device model `{model_key}` is catalogued but does not have an executable adapter yet."
            )
        return entry.adapter

    def _sorted_entries(self) -> list[DeviceCatalogEntry]:
        return sorted(self._entries.values(), key=lambda entry: entry.descriptor.label.lower())


def build_default_catalog(settings: GatewaySettings) -> DeviceAdapterCatalog:
    nabaztag_tag_adapter = NabaztagTagAdapter(settings)
    return DeviceAdapterCatalog(
        entries=[
            DeviceCatalogEntry(
                descriptor=_planned_nabaztag_v1_descriptor(),
                adapter=None,
            ),
            DeviceCatalogEntry(
                descriptor=nabaztag_tag_adapter.descriptor(),
                adapter=nabaztag_tag_adapter,
            ),
            DeviceCatalogEntry(
                descriptor=_planned_karotz_descriptor(),
                adapter=None,
            ),
        ]
    )


def _planned_nabaztag_v1_descriptor() -> DeviceModelDescriptor:
    return DeviceModelDescriptor(
        key="nabaztag-v1",
        family=DeviceFamily.NABAZTAG_V1,
        label="Nabaztag v1",
        implementation_status=ImplementationStatus.PLANNED,
        transport="legacy device integration to be specified",
        summary=(
            "Future adapter target for first-generation Nabaztag devices. The capability matrix is "
            "kept intentionally conservative until the v1 transport contract is documented."
        ),
        implementation_notes=(
            "The architecture already reserves a dedicated model key for v1 so the portal, API and MCP "
            "surfaces can target it independently from Nabaztag:tag."
        ),
        documentation_refs=[
            "docs/device-platform-architecture.md",
            "docs/nabaztag-protocol-research.md",
        ],
        surfaces=["api", "mcp"],
        primitives=[
            PrimitiveSupportDescriptor(
                primitive=StandardPrimitive.CONNECT,
                status=PrimitiveSupportStatus.PLANNED,
                summary="Independent v1 connection flow will be implemented through a dedicated adapter.",
            ),
            PrimitiveSupportDescriptor(
                primitive=StandardPrimitive.DISCONNECT,
                status=PrimitiveSupportStatus.PLANNED,
                summary="Independent v1 disconnection flow will be implemented through a dedicated adapter.",
            ),
            PrimitiveSupportDescriptor(
                primitive=StandardPrimitive.SYNC,
                status=PrimitiveSupportStatus.PLANNED,
                summary="Normalized v1 state sync remains to be specified.",
            ),
            PrimitiveSupportDescriptor(
                primitive=StandardPrimitive.SLEEP,
                status=PrimitiveSupportStatus.PLANNED,
                summary="Sleep/wakeup semantics need device-specific confirmation for v1.",
            ),
            PrimitiveSupportDescriptor(
                primitive=StandardPrimitive.WAKEUP,
                status=PrimitiveSupportStatus.PLANNED,
                summary="Sleep/wakeup semantics need device-specific confirmation for v1.",
            ),
            PrimitiveSupportDescriptor(
                primitive=StandardPrimitive.EARS_MOVE,
                status=PrimitiveSupportStatus.PLANNED,
                summary="Ear control will be normalized once the v1 transport adapter exists.",
            ),
            PrimitiveSupportDescriptor(
                primitive=StandardPrimitive.LED_SET,
                status=PrimitiveSupportStatus.PLANNED,
                summary="LED support will be normalized once the v1 transport adapter exists.",
            ),
            PrimitiveSupportDescriptor(
                primitive=StandardPrimitive.AUDIO_PLAY,
                status=PrimitiveSupportStatus.PLANNED,
                summary="Audio playback is part of the planned v1 adapter surface.",
            ),
            PrimitiveSupportDescriptor(
                primitive=StandardPrimitive.AUDIO_RECORDING_START,
                status=PrimitiveSupportStatus.UNSUPPORTED,
                summary="v1 is explicitly modeled without microphone capture.",
            ),
            PrimitiveSupportDescriptor(
                primitive=StandardPrimitive.AUDIO_RECORDING_STOP,
                status=PrimitiveSupportStatus.UNSUPPORTED,
                summary="v1 is explicitly modeled without microphone capture.",
            ),
            PrimitiveSupportDescriptor(
                primitive=StandardPrimitive.VIDEO_SNAPSHOT,
                status=PrimitiveSupportStatus.UNSUPPORTED,
                summary="v1 does not expose video capture.",
            ),
            PrimitiveSupportDescriptor(
                primitive=StandardPrimitive.VIDEO_STREAM_START,
                status=PrimitiveSupportStatus.UNSUPPORTED,
                summary="v1 does not expose video capture.",
            ),
            PrimitiveSupportDescriptor(
                primitive=StandardPrimitive.VIDEO_STREAM_STOP,
                status=PrimitiveSupportStatus.UNSUPPORTED,
                summary="v1 does not expose video capture.",
            ),
        ],
    )


def _planned_karotz_descriptor() -> DeviceModelDescriptor:
    return DeviceModelDescriptor(
        key="karotz",
        family=DeviceFamily.KAROTZ,
        label="Karotz",
        implementation_status=ImplementationStatus.PLANNED,
        transport="karotz integration to be specified",
        summary=(
            "Future adapter target for Karotz devices. The standardized layer already reserves video "
            "capture primitives for it, while keeping the rest of the contract explicit and independent."
        ),
        implementation_notes=(
            "The Karotz adapter is planned as a first-class device family rather than a special case. "
            "Video support is kept in the public primitive contract from day one."
        ),
        documentation_refs=["docs/device-platform-architecture.md"],
        surfaces=["api", "mcp"],
        primitives=[
            PrimitiveSupportDescriptor(
                primitive=StandardPrimitive.CONNECT,
                status=PrimitiveSupportStatus.PLANNED,
                summary="Independent Karotz connection flow will be implemented through a dedicated adapter.",
            ),
            PrimitiveSupportDescriptor(
                primitive=StandardPrimitive.DISCONNECT,
                status=PrimitiveSupportStatus.PLANNED,
                summary="Independent Karotz disconnection flow will be implemented through a dedicated adapter.",
            ),
            PrimitiveSupportDescriptor(
                primitive=StandardPrimitive.SYNC,
                status=PrimitiveSupportStatus.PLANNED,
                summary="Normalized Karotz state sync remains to be specified.",
            ),
            PrimitiveSupportDescriptor(
                primitive=StandardPrimitive.SLEEP,
                status=PrimitiveSupportStatus.PLANNED,
                summary="Karotz sleep semantics remain to be specified.",
            ),
            PrimitiveSupportDescriptor(
                primitive=StandardPrimitive.WAKEUP,
                status=PrimitiveSupportStatus.PLANNED,
                summary="Karotz wakeup semantics remain to be specified.",
            ),
            PrimitiveSupportDescriptor(
                primitive=StandardPrimitive.EARS_MOVE,
                status=PrimitiveSupportStatus.PLANNED,
                summary="Ear control will be normalized once the Karotz adapter exists.",
            ),
            PrimitiveSupportDescriptor(
                primitive=StandardPrimitive.LED_SET,
                status=PrimitiveSupportStatus.PLANNED,
                summary="LED support will be normalized once the Karotz adapter exists.",
            ),
            PrimitiveSupportDescriptor(
                primitive=StandardPrimitive.AUDIO_PLAY,
                status=PrimitiveSupportStatus.PLANNED,
                summary="Audio playback is part of the planned Karotz adapter surface.",
            ),
            PrimitiveSupportDescriptor(
                primitive=StandardPrimitive.AUDIO_RECORDING_START,
                status=PrimitiveSupportStatus.PLANNED,
                summary="Audio recording is expected to be normalized in the future Karotz adapter.",
            ),
            PrimitiveSupportDescriptor(
                primitive=StandardPrimitive.AUDIO_RECORDING_STOP,
                status=PrimitiveSupportStatus.PLANNED,
                summary="Audio recording is expected to be normalized in the future Karotz adapter.",
            ),
            PrimitiveSupportDescriptor(
                primitive=StandardPrimitive.VIDEO_SNAPSHOT,
                status=PrimitiveSupportStatus.PLANNED,
                summary="The standardized API already reserves a still-image capture primitive for Karotz.",
            ),
            PrimitiveSupportDescriptor(
                primitive=StandardPrimitive.VIDEO_STREAM_START,
                status=PrimitiveSupportStatus.PLANNED,
                summary="The standardized API already reserves a video stream primitive for Karotz.",
            ),
            PrimitiveSupportDescriptor(
                primitive=StandardPrimitive.VIDEO_STREAM_STOP,
                status=PrimitiveSupportStatus.PLANNED,
                summary="The standardized API already reserves a video stream primitive for Karotz.",
            ),
        ],
    )
