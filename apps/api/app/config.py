from __future__ import annotations

import os

from .settings import GatewaySettings


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def load_gateway_settings() -> GatewaySettings:
    return GatewaySettings(
        driver=os.getenv("NABAZTAG_GATEWAY_DRIVER", "simulated"),
        host=os.getenv("NABAZTAG_GATEWAY_HOST", "127.0.0.1"),
        port=int(os.getenv("NABAZTAG_GATEWAY_PORT", "10543")),
        username=os.getenv("NABAZTAG_GATEWAY_USERNAME"),
        password=os.getenv("NABAZTAG_GATEWAY_PASSWORD"),
        use_tls=_env_bool("NABAZTAG_GATEWAY_TLS", False),
        connect_timeout_seconds=float(os.getenv("NABAZTAG_GATEWAY_TIMEOUT", "5")),
        read_timeout_seconds=float(os.getenv("NABAZTAG_GATEWAY_READ_TIMEOUT", "10")),
    )
