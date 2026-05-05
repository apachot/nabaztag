from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..config import load_gateway_settings
from ..settings import GatewayError
from .errors import AdapterNotAvailableError, UnknownDeviceModelError, UnsupportedPrimitiveError
from .models import (
    DeviceExecutionRequest,
    DeviceExecutionResult,
    DeviceModelListResponse,
    DeviceModelResponse,
    DeviceProbeRequest,
    DeviceProbeResult,
)
from .service import create_device_platform_service

router = APIRouter(prefix="/api/device-platform", tags=["device-platform"])
service = create_device_platform_service(load_gateway_settings())


def _device_platform_http_exception(exc: Exception) -> HTTPException:
    if isinstance(exc, UnknownDeviceModelError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, (AdapterNotAvailableError, UnsupportedPrimitiveError)):
        return HTTPException(status_code=501, detail=str(exc))
    if isinstance(exc, GatewayError):
        return HTTPException(status_code=502, detail=str(exc))
    raise exc


@router.get("/models", response_model=DeviceModelListResponse)
def list_device_models() -> DeviceModelListResponse:
    return DeviceModelListResponse(models=service.list_models())


@router.get("/models/{model_key}", response_model=DeviceModelResponse)
def get_device_model(model_key: str) -> DeviceModelResponse:
    try:
        return DeviceModelResponse(model=service.get_model(model_key))
    except Exception as exc:
        raise _device_platform_http_exception(exc) from exc


@router.post("/probe", response_model=DeviceProbeResult)
def probe_device(payload: DeviceProbeRequest) -> DeviceProbeResult:
    try:
        return service.probe(payload)
    except Exception as exc:
        raise _device_platform_http_exception(exc) from exc


@router.post("/execute", response_model=DeviceExecutionResult)
def execute_device_primitive(payload: DeviceExecutionRequest) -> DeviceExecutionResult:
    try:
        return service.execute(payload)
    except Exception as exc:
        raise _device_platform_http_exception(exc) from exc
