from __future__ import annotations

from dataclasses import dataclass
import importlib
import json
from pathlib import Path
from typing import Callable


@dataclass(frozen=True, slots=True)
class RabbitPluginHook:
    pipeline: str
    handler: str


@dataclass(frozen=True, slots=True)
class RabbitPluginDefinition:
    plugin_id: str
    label: str
    description: str
    category: str
    default_enabled: bool = False
    experimental: bool = False
    hooks: tuple[RabbitPluginHook, ...] = ()
    manifest_path: str | None = None


def _plugins_root() -> Path:
    return Path(__file__).resolve().parent


def _load_plugin_definition(plugin_dir: Path) -> RabbitPluginDefinition | None:
    manifest_path = plugin_dir / "plugin.json"
    if not manifest_path.exists():
        return None
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    plugin_id = str(payload.get("plugin_id") or plugin_dir.name).strip().lower()
    hooks_payload = payload.get("hooks") or []
    hooks: list[RabbitPluginHook] = []
    for item in hooks_payload:
        if not isinstance(item, dict):
            continue
        pipeline = str(item.get("pipeline") or "").strip()
        handler = str(item.get("handler") or "").strip()
        if not pipeline or not handler:
            continue
        hooks.append(RabbitPluginHook(pipeline=pipeline, handler=handler))
    return RabbitPluginDefinition(
        plugin_id=plugin_id,
        label=str(payload.get("label") or plugin_id).strip(),
        description=str(payload.get("description") or "").strip(),
        category=str(payload.get("category") or "misc").strip(),
        default_enabled=bool(payload.get("default_enabled", False)),
        experimental=bool(payload.get("experimental", False)),
        hooks=tuple(hooks),
        manifest_path=str(manifest_path),
    )


def get_plugin_definitions() -> list[RabbitPluginDefinition]:
    definitions: list[RabbitPluginDefinition] = []
    for plugin_dir in sorted(_plugins_root().iterdir()):
        if not plugin_dir.is_dir() or plugin_dir.name == "__pycache__":
            continue
        definition = _load_plugin_definition(plugin_dir)
        if definition is not None:
            definitions.append(definition)
    return definitions


def get_plugin_definition(plugin_id: str) -> RabbitPluginDefinition | None:
    normalized = plugin_id.strip().lower()
    for plugin in get_plugin_definitions():
        if plugin.plugin_id == normalized:
            return plugin
    return None


def get_plugin_hooks_for_pipeline(pipeline_name: str) -> list[tuple[RabbitPluginDefinition, RabbitPluginHook]]:
    hooks: list[tuple[RabbitPluginDefinition, RabbitPluginHook]] = []
    for plugin in get_plugin_definitions():
        for hook in plugin.hooks:
            if hook.pipeline == pipeline_name:
                hooks.append((plugin, hook))
    return hooks


def resolve_plugin_handler(plugin: RabbitPluginDefinition, hook: RabbitPluginHook) -> Callable:
    module_path, _, attribute_name = hook.handler.rpartition(".")
    if not module_path or not attribute_name:
        raise RuntimeError(
            f"Plugin `{plugin.plugin_id}` declare un handler invalide `{hook.handler}` "
            f"dans `{hook.pipeline}`."
        )
    module = importlib.import_module(f"{__name__}.{plugin.plugin_id}.{module_path}")
    handler = getattr(module, attribute_name, None)
    if handler is None or not callable(handler):
        raise RuntimeError(
            f"Le handler `{hook.handler}` du plugin `{plugin.plugin_id}` est introuvable ou non callable."
        )
    return handler
