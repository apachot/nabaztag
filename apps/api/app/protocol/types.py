from __future__ import annotations

from datetime import datetime
from dataclasses import dataclass, field
import json

from ..models import ConnectionStatus, utc_now


@dataclass(frozen=True)
class ProtocolCommandEnvelope:
    kind: str
    payload: dict

    def to_json_line(self) -> bytes:
        return (json.dumps(self.payload, separators=(",", ":")) + "\r\n").encode("utf-8")


@dataclass(frozen=True)
class ProtocolEventEnvelope:
    kind: str
    connection_status: ConnectionStatus | None = None
    state_delta: dict = field(default_factory=dict)
    payload: dict = field(default_factory=dict)
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class ProtocolResponseEnvelope:
    status: str
    request_id: str | None = None
    payload: dict = field(default_factory=dict)
