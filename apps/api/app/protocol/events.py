from __future__ import annotations

from ..models import ConnectionStatus, Rabbit, RabbitState, RabbitSync, utc_now
from .types import ProtocolEventEnvelope


def sync_from_event(rabbit: Rabbit, event: ProtocolEventEnvelope) -> RabbitSync:
    rabbit_copy = rabbit.model_copy(deep=True)

    if event.connection_status is not None:
        rabbit_copy.connection_status = event.connection_status

    if event.state_delta:
        rabbit_copy.state = _merge_state(rabbit_copy.state, event.state_delta)

    rabbit_copy.updated_at = utc_now()
    return RabbitSync(rabbit=rabbit_copy, synced_at=event.occurred_at)


def offline_sync(rabbit: Rabbit) -> RabbitSync:
    rabbit_copy = rabbit.model_copy(deep=True)
    rabbit_copy.connection_status = ConnectionStatus.OFFLINE
    rabbit_copy.updated_at = utc_now()
    return RabbitSync(rabbit=rabbit_copy)


def state_event_from_packet(packet: dict) -> ProtocolEventEnvelope:
    state = packet.get("state")
    return ProtocolEventEnvelope(
        kind="rabbit.state",
        connection_status=_map_state_to_connection_status(state),
        payload=packet,
    )


def _merge_state(state: RabbitState, delta: dict) -> RabbitState:
    merged = state.model_copy(deep=True)
    for key, value in delta.items():
        if hasattr(merged, key):
            setattr(merged, key, value)
    return merged


def _map_state_to_connection_status(state: str | None) -> ConnectionStatus:
    if state in {"idle", "interactive", "playing"}:
        return ConnectionStatus.ONLINE
    return ConnectionStatus.OFFLINE
