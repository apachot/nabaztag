from __future__ import annotations

from collections import defaultdict, deque
from .models import (
    Command,
    CommandType,
    ConnectionStatus,
    Event,
    Rabbit,
    RabbitCreate,
)


class InMemoryStore:
    def __init__(self) -> None:
        self.rabbits: dict[str, Rabbit] = {}
        self.events: dict[str, deque[Event]] = defaultdict(lambda: deque(maxlen=100))
        self.commands: dict[str, deque[Command]] = defaultdict(lambda: deque(maxlen=100))

        demo = Rabbit(
            slug="mon-lapin",
            name="Mon lapin",
            connection_status=ConnectionStatus.SIMULATED,
        )
        self.rabbits[demo.id] = demo
        self.append_event(
            demo.id,
            "rabbit.connected",
            "Rabbit simulator ready",
            {"connection_status": demo.connection_status},
        )

    def list_rabbits(self) -> list[Rabbit]:
        return sorted(self.rabbits.values(), key=lambda rabbit: rabbit.created_at)

    def create_rabbit(self, payload: RabbitCreate) -> Rabbit:
        rabbit = Rabbit(slug=payload.slug, name=payload.name)
        self.rabbits[rabbit.id] = rabbit
        self.append_event(rabbit.id, "rabbit.created", "Rabbit registered", payload.model_dump())
        return rabbit

    def replace_rabbit(self, rabbit: Rabbit) -> Rabbit:
        self.rabbits[rabbit.id] = rabbit
        return rabbit

    def get_rabbit(self, rabbit_id: str) -> Rabbit:
        return self.rabbits[rabbit_id]

    def list_events(self, rabbit_id: str) -> list[Event]:
        return list(reversed(self.events[rabbit_id]))

    def list_commands(self, rabbit_id: str) -> list[Command]:
        return list(reversed(self.commands[rabbit_id]))

    def append_event(self, rabbit_id: str, event_type: str, message: str, payload: dict) -> Event:
        event = Event(rabbit_id=rabbit_id, type=event_type, message=message, payload=payload)
        self.events[rabbit_id].append(event)
        return event

    def queue_command(self, rabbit_id: str, command_type: CommandType, payload: dict) -> Command:
        command = Command(rabbit_id=rabbit_id, type=command_type, payload=payload)
        self.commands[rabbit_id].append(command)
        return command


store = InMemoryStore()
