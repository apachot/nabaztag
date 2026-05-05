from __future__ import annotations


class DevicePlatformError(RuntimeError):
    pass


class UnknownDeviceModelError(DevicePlatformError):
    pass


class AdapterNotAvailableError(DevicePlatformError):
    pass


class UnsupportedPrimitiveError(DevicePlatformError):
    pass
