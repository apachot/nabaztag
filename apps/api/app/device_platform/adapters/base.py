from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import (
    DeviceExecutionResult,
    DeviceModelDescriptor,
    DeviceProbeResult,
    DeviceTarget,
    StandardizedPrimitiveRequest,
)


class DeviceAdapter(ABC):
    @property
    @abstractmethod
    def model_key(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def descriptor(self) -> DeviceModelDescriptor:
        raise NotImplementedError

    @abstractmethod
    def probe(self, target: DeviceTarget) -> DeviceProbeResult:
        raise NotImplementedError

    @abstractmethod
    def execute(
        self,
        target: DeviceTarget,
        command: StandardizedPrimitiveRequest,
    ) -> DeviceExecutionResult:
        raise NotImplementedError
