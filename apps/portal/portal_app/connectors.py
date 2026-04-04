from __future__ import annotations

import json
from dataclasses import dataclass
from urllib import error as urllib_error
from urllib import request as urllib_request

from flask import current_app

from .extensions import db
from .models import UserConnectorConfig

HOME_ASSISTANT_SUPPORTED_DOMAINS = (
    "light",
    "switch",
    "scene",
    "script",
    "media_player",
    "input_boolean",
)

HOME_ASSISTANT_DOMAIN_SERVICES = {
    "light": ["turn_on", "turn_off", "toggle"],
    "switch": ["turn_on", "turn_off", "toggle"],
    "scene": ["turn_on"],
    "script": ["turn_on"],
    "media_player": ["media_play", "media_pause", "media_stop", "turn_on", "turn_off", "volume_set"],
    "input_boolean": ["turn_on", "turn_off", "toggle"],
}


@dataclass(frozen=True)
class ConnectorDefinition:
    key: str
    label: str
    description: str
    account_fields: tuple[dict, ...]


CONNECTOR_REGISTRY = {
    "home_assistant": ConnectorDefinition(
        key="home_assistant",
        label="Home Assistant",
        description=(
            "Connecte le lapin a une instance domotique existante via URL distante et token."
        ),
        account_fields=(
            {
                "name": "base_url",
                "label": "URL du connecteur",
                "type": "url",
                "placeholder": "https://xxxx.ui.nabu.casa",
            },
            {
                "name": "token",
                "label": "Token d'accès long terme",
                "type": "password",
                "placeholder": "Token déjà enregistré",
            },
        ),
    ),
}


def connector_definitions() -> list[ConnectorDefinition]:
    return list(CONNECTOR_REGISTRY.values())


def connector_definition(connector_key: str) -> ConnectorDefinition | None:
    return CONNECTOR_REGISTRY.get(connector_key)


def get_user_connector(user, connector_key: str) -> UserConnectorConfig | None:
    return UserConnectorConfig.query.filter_by(user_id=user.id, key=connector_key).first()


def get_user_connector_config(user, connector_key: str) -> dict:
    record = get_user_connector(user, connector_key)
    if record is None:
        return {}
    return record.config_dict()


def save_user_connector_config(user, connector_key: str, config: dict) -> UserConnectorConfig:
    record = get_user_connector(user, connector_key)
    if record is None:
        record = UserConnectorConfig(user_id=user.id, key=connector_key)
    record.set_config(config)
    db.session.add(record)
    return record


def clear_user_connector_config(user, connector_key: str) -> bool:
    record = get_user_connector(user, connector_key)
    if record is None:
        return False
    db.session.delete(record)
    return True


def is_connector_configured(user, connector_key: str) -> bool:
    if connector_key == "home_assistant":
        config = get_user_connector_config(user, connector_key)
        return bool(_normalize_home_assistant_url(config.get("base_url")) and config.get("token"))
    return False


def connector_action_catalog(user) -> list[dict]:
    catalog: list[dict] = []
    if is_connector_configured(user, "home_assistant"):
        catalog.append(
            {
                "name": "connector.invoke",
                "description": "Appeler un connecteur externe configure pour ce compte.",
                "parameters": {
                    "connector": "home_assistant",
                    "operation": "call_service",
                    "params": {
                        "domain": "light|switch|scene|script|media_player|input_boolean",
                        "service": "nom du service, par exemple turn_on",
                        "entity_id": "entity_id optionnel mais recommande",
                        "service_data": "objet JSON optionnel",
                    },
                },
            }
        )
    return catalog


def connector_context_for_user(user) -> dict:
    context: dict[str, dict] = {}
    if is_connector_configured(user, "home_assistant"):
        try:
            context["home_assistant"] = {
                "operations": ["call_service"],
                "domains": list(HOME_ASSISTANT_SUPPORTED_DOMAINS),
                "services_by_domain": HOME_ASSISTANT_DOMAIN_SERVICES,
                "entities": _home_assistant_entities(user),
            }
        except RuntimeError as exc:
            current_app.logger.warning("unable to load connector context for user %s: %s", user.id, exc)
    return context


def connector_context_for_rabbit(rabbit) -> dict:
    owner = rabbit.owner
    if owner is None:
        return {}
    return connector_context_for_user(owner)


def normalize_connector_action(action_payload: object) -> dict | None:
    if not isinstance(action_payload, dict):
        return None
    connector_key = " ".join(str(action_payload.get("connector") or "").split()).strip().lower()
    operation = " ".join(str(action_payload.get("operation") or "").split()).strip().lower()
    params = action_payload.get("params")
    if connector_key != "home_assistant" or operation != "call_service" or not isinstance(params, dict):
        return None
    domain = str(params.get("domain") or "").strip().lower()
    service = str(params.get("service") or "").strip().lower()
    entity_id = " ".join(str(params.get("entity_id") or "").split()).strip()
    service_data = params.get("service_data")
    if domain not in HOME_ASSISTANT_SUPPORTED_DOMAINS or not service:
        return None
    if service_data is not None and not isinstance(service_data, dict):
        return None
    normalized = {
        "name": "connector.invoke",
        "connector": connector_key,
        "operation": operation,
        "params": {
            "domain": domain,
            "service": service,
        },
    }
    if entity_id:
        normalized["params"]["entity_id"] = entity_id
    if isinstance(service_data, dict) and service_data:
        normalized["params"]["service_data"] = service_data
    return normalized


def execute_connector_action(user, action: dict) -> None:
    connector_key = action.get("connector")
    operation = action.get("operation")
    params = action.get("params")
    if connector_key == "home_assistant" and operation == "call_service" and isinstance(params, dict):
        _execute_home_assistant_service(user, params)
        return
    raise RuntimeError("Action de connecteur invalide.")


def connector_test_contexts(user) -> list[dict]:
    contexts: list[dict] = []
    if is_connector_configured(user, "home_assistant"):
        error = None
        entities: list[dict] = []
        try:
            entities = _home_assistant_entities(user)
        except RuntimeError as exc:
            error = str(exc)
        contexts.append(
            {
                "key": "home_assistant",
                "label": "Home Assistant",
                "description": "Teste un service du connecteur domotique configure pour ce compte.",
                "entities": entities,
                "error": error,
            }
        )
    return contexts


def _normalize_home_assistant_url(url: str | None) -> str:
    normalized = " ".join(str(url or "").split()).strip()
    if not normalized:
        return ""
    if not normalized.startswith(("http://", "https://")):
        normalized = f"http://{normalized}"
    return normalized.rstrip("/")


def _home_assistant_api_request(
    user,
    *,
    method: str,
    path: str,
    payload: dict | None = None,
    timeout: int = 10,
):
    config = get_user_connector_config(user, "home_assistant")
    base_url = _normalize_home_assistant_url(config.get("base_url"))
    token = str(config.get("token") or "").strip()
    if not base_url or not token:
        raise RuntimeError("Le connecteur Home Assistant n'est pas configuré pour ce compte.")
    body = None
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request_object = urllib_request.Request(
        f"{base_url}{path}",
        data=body,
        headers=headers,
        method=method.upper(),
    )
    try:
        with urllib_request.urlopen(request_object, timeout=timeout) as response:
            raw_body = response.read().decode("utf-8")
    except urllib_error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore").strip()
        message = detail or exc.reason or f"HTTP {exc.code}"
        raise RuntimeError(f"Home Assistant a répondu en erreur: {message}") from exc
    except urllib_error.URLError as exc:
        raise RuntimeError(f"Impossible de joindre Home Assistant: {exc.reason}") from exc
    if not raw_body:
        return None
    try:
        return json.loads(raw_body)
    except json.JSONDecodeError:
        return raw_body


def _home_assistant_entities(user, *, limit: int = 60) -> list[dict]:
    payload = _home_assistant_api_request(user, method="GET", path="/api/states")
    if not isinstance(payload, list):
        return []
    entities: list[dict] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        entity_id = str(item.get("entity_id") or "").strip()
        if "." not in entity_id:
            continue
        domain, _ = entity_id.split(".", 1)
        if domain not in HOME_ASSISTANT_SUPPORTED_DOMAINS:
            continue
        attributes = item.get("attributes") if isinstance(item.get("attributes"), dict) else {}
        entities.append(
            {
                "entity_id": entity_id,
                "domain": domain,
                "name": str(attributes.get("friendly_name") or entity_id).strip(),
                "state": item.get("state"),
                "supported_services": HOME_ASSISTANT_DOMAIN_SERVICES.get(domain, []),
            }
        )
    entities.sort(key=lambda entity: (entity["domain"], entity["name"].lower(), entity["entity_id"]))
    return entities[:limit]


def _execute_home_assistant_service(user, params: dict) -> None:
    domain = str(params.get("domain") or "").strip().lower()
    service = str(params.get("service") or "").strip().lower()
    entity_id = " ".join(str(params.get("entity_id") or "").split()).strip()
    if domain not in HOME_ASSISTANT_SUPPORTED_DOMAINS or not service:
        raise RuntimeError("Action Home Assistant invalide.")
    service_data = params.get("service_data")
    if not isinstance(service_data, dict):
        service_data = {}
    payload = dict(service_data)
    if entity_id:
        payload["entity_id"] = entity_id
    _home_assistant_api_request(
        user,
        method="POST",
        path=f"/api/services/{domain}/{service}",
        payload=payload,
    )
