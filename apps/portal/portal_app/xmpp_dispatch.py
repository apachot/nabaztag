from __future__ import annotations

from collections import deque
from typing import Mapping, Sequence, TypeVar

T = TypeVar("T")


def build_round_robin_batch(
    queues_by_serial: Mapping[str, Sequence[T]],
    *,
    oldest_by_serial: Mapping[str, object],
    limit: int,
) -> list[T]:
    if limit <= 0:
        return []

    pending = {serial: deque(items) for serial, items in queues_by_serial.items() if items}
    if not pending:
        return []

    serial_order = sorted(
        pending,
        key=lambda serial: (oldest_by_serial.get(serial) is None, oldest_by_serial.get(serial), serial),
    )

    batch: list[T] = []
    while serial_order and len(batch) < limit:
        next_round: list[str] = []
        for serial in serial_order:
            queue = pending.get(serial)
            if not queue:
                continue
            batch.append(queue.popleft())
            if queue:
                next_round.append(serial)
            if len(batch) >= limit:
                break
        serial_order = next_round

    return batch
