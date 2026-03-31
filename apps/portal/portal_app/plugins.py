from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RabbitPluginDefinition:
    plugin_id: str
    label: str
    description: str
    category: str
    default_enabled: bool = False
    experimental: bool = False


PLUGIN_REGISTRY: tuple[RabbitPluginDefinition, ...] = (
    RabbitPluginDefinition(
        plugin_id="use_cases",
        label="Laboratoire d'usages",
        description="Scènes expressives, improvisation, radio et scénarios Ztamp pour explorer rapidement de nouveaux usages.",
        category="experience",
        default_enabled=True,
    ),
    RabbitPluginDefinition(
        plugin_id="spotify",
        label="Spotify",
        description="Pont futur vers un récepteur Spotify Connect et un flux audio relu par le lapin.",
        category="media",
        experimental=True,
    ),
    RabbitPluginDefinition(
        plugin_id="calendar",
        label="Calendrier",
        description="Lecture d'agenda, rappels et résumés contextuels depuis un service externe.",
        category="assistant",
        experimental=True,
    ),
    RabbitPluginDefinition(
        plugin_id="mail",
        label="Mail",
        description="Notifications de messages importants et résumés vocaux de la boîte de réception.",
        category="assistant",
        experimental=True,
    ),
)


def get_plugin_definitions() -> list[RabbitPluginDefinition]:
    return list(PLUGIN_REGISTRY)


def get_plugin_definition(plugin_id: str) -> RabbitPluginDefinition | None:
    normalized = plugin_id.strip().lower()
    for plugin in PLUGIN_REGISTRY:
        if plugin.plugin_id == normalized:
            return plugin
    return None
