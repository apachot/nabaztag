from __future__ import annotations

from .config import load_gateway_settings
from .gateway import NabaztagProtocolGateway, RabbitGateway, SimulatedRabbitGateway
from .settings import GatewaySettings
from .service import RabbitService
from .store import store


def create_gateway(settings: GatewaySettings) -> RabbitGateway:
    if settings.driver == "simulated":
        return SimulatedRabbitGateway()
    if settings.driver == "protocol":
        return NabaztagProtocolGateway(settings)
    raise ValueError(f"Unsupported gateway driver: {settings.driver}")


def create_service() -> RabbitService:
    settings = load_gateway_settings()
    gateway = create_gateway(settings)
    return RabbitService(store, gateway)
