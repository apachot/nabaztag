from __future__ import annotations

from ..settings import GatewaySettings
from .catalog import DeviceAdapterCatalog, build_default_catalog
from .models import (
    DeviceExecutionRequest,
    DeviceExecutionResult,
    DeviceModelDescriptor,
    DeviceProbeRequest,
    DeviceProbeResult,
)


class DevicePlatformService:
    def __init__(self, catalog: DeviceAdapterCatalog) -> None:
        self.catalog = catalog

    def list_models(self) -> list[DeviceModelDescriptor]:
        return self.catalog.list_models()

    def get_model(self, model_key: str) -> DeviceModelDescriptor:
        return self.catalog.get_descriptor(model_key)

    def probe(self, payload: DeviceProbeRequest) -> DeviceProbeResult:
        adapter = self.catalog.get_adapter(payload.model_key)
        return adapter.probe(payload.target)

    def execute(self, payload: DeviceExecutionRequest) -> DeviceExecutionResult:
        adapter = self.catalog.get_adapter(payload.model_key)
        return adapter.execute(payload.target, payload.command)


def create_device_platform_service(settings: GatewaySettings) -> DevicePlatformService:
    return DevicePlatformService(build_default_catalog(settings))
