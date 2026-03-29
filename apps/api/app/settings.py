from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GatewaySettings:
    driver: str = "simulated"
    host: str = "127.0.0.1"
    port: int = 10543
    username: str | None = None
    password: str | None = None
    use_tls: bool = False
    connect_timeout_seconds: float = 5.0
    read_timeout_seconds: float = 10.0


class GatewayError(RuntimeError):
    pass
