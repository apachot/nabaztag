from __future__ import annotations

import json
from dataclasses import asdict, dataclass
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
class ConnectorFieldDefinition:
    name: str
    label: str
    type: str
    placeholder: str = ""
    help_text: str = ""


@dataclass(frozen=True)
class ConnectorOperationDefinition:
    key: str
    description: str
    params_schema: dict


@dataclass(frozen=True)
class ConnectorTestFieldDefinition:
    name: str
    label: str
    type: str
    placeholder: str = ""
    options_key: str | None = None


@dataclass(frozen=True)
class ConnectorTestFormDefinition:
    description: str
    fields: tuple[ConnectorTestFieldDefinition, ...]


@dataclass(frozen=True)
class ConnectorDefinition:
    key: str
    label: str
    description: str
    account_fields: tuple[ConnectorFieldDefinition, ...]
    operations: tuple[ConnectorOperationDefinition, ...]
    test_form: ConnectorTestFormDefinition | None = None


CONNECTOR_REGISTRY = {
    "home_assistant": ConnectorDefinition(
        key="home_assistant",
        label="Home Assistant",
        description="Connecte le lapin a une instance domotique existante via URL distante et token.",
        account_fields=(
            ConnectorFieldDefinition(
                name="base_url",
                label="URL du connecteur",
                type="url",
                placeholder="https://xxxx.ui.nabu.casa",
            ),
            ConnectorFieldDefinition(
                name="token",
                label="Token d'accès long terme",
                type="password",
                placeholder="Token déjà enregistré",
            ),
        ),
        operations=(
            ConnectorOperationDefinition(
                key="call_service",
                description="Appeler un service Home Assistant sur une entite connue.",
                params_schema={
                    "domain": "light|switch|scene|script|media_player|input_boolean",
                    "service": "nom du service Home Assistant, par exemple turn_on",
                    "entity_id": "entity_id optionnel mais recommande",
                    "service_data": "objet JSON optionnel",
                },
            ),
        ),
        test_form=ConnectorTestFormDefinition(
            description="Teste un service Home Assistant depuis la fiche du lapin.",
            fields=(
                ConnectorTestFieldDefinition("entity_id", "Entité", "select", options_key="entities"),
                ConnectorTestFieldDefinition("domain", "Domaine", "text", "light"),
                ConnectorTestFieldDefinition("service", "Service", "text", "turn_on"),
                ConnectorTestFieldDefinition("service_data", "Paramètres JSON optionnels", "textarea", '{"rgb_color":[0,0,255]}'),
            ),
        ),
    ),
    "webhook": ConnectorDefinition(
        key="webhook",
        label="Webhook",
        description="Declenche un endpoint HTTP externe auto-heberge pour integrer des automatismes ou un bridge local.",
        account_fields=(
            ConnectorFieldDefinition(
                name="endpoint_url",
                label="URL du webhook",
                type="url",
                placeholder="https://bridge.local.example/hooks/nabaztag",
            ),
            ConnectorFieldDefinition(
                name="token",
                label="Bearer token optionnel",
                type="password",
                placeholder="Token déjà enregistré",
                help_text="Si renseigne, le portail enverra Authorization: Bearer <token>.",
            ),
        ),
        operations=(
            ConnectorOperationDefinition(
                key="trigger",
                description="Declencher un webhook HTTP POST avec un nom d'evenement et un payload JSON.",
                params_schema={
                    "event": "nom d'evenement libre, par exemple play_music",
                    "payload": "objet JSON optionnel avec les parametres de l'appel",
                },
            ),
        ),
        test_form=ConnectorTestFormDefinition(
            description="Teste un appel HTTP POST sortant vers un webhook externe.",
            fields=(
                ConnectorTestFieldDefinition("event", "Événement", "text", "play_music"),
                ConnectorTestFieldDefinition("payload", "Payload JSON optionnel", "textarea", '{"artist":"Leonard Cohen"}'),
            ),
        ),
    ),
}


def connector_definitions() -> list[ConnectorDefinition]:
    return list(CONNECTOR_REGISTRY.values())


def connector_definition(connector_key: str) -> ConnectorDefinition | None:
    return CONNECTOR_REGISTRY.get(connector_key)


def connector_contract() -> list[dict]:
    contract: list[dict] = []
    for definition in connector_definitions():
        contract.append(
            {
                "key": definition.key,
                "label": definition.label,
                "description": definition.description,
                "account_fields": [asdict(field) for field in definition.account_fields],
                "operations": [asdict(operation) for operation in definition.operations],
                "test_form": asdict(definition.test_form) if definition.test_form is not None else None,
            }
        )
    return contract


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
    config = get_user_connector_config(user, connector_key)
    if connector_key == "home_assistant":
        return bool(_normalize_url(config.get("base_url")) and config.get("token"))
    if connector_key == "webhook":
        return bool(_normalize_url(config.get("endpoint_url")))
    return False


def connector_action_catalog(user) -> list[dict]:
    catalog: list[dict] = []
    for definition in connector_definitions():
        if not is_connector_configured(user, definition.key):
            continue
        for operation in definition.operations:
            catalog.append(
                {
                    "name": "connector.invoke",
                    "description": f"{definition.label}: {operation.description}",
                    "parameters": {
                        "connector": definition.key,
                        "operation": operation.key,
                        "params": operation.params_schema,
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
    if is_connector_configured(user, "webhook"):
        context["webhook"] = {
            "operations": ["trigger"],
            "description": "Webhook HTTP POST configurable vers un service ou un bridge local.",
        }
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
    if not isinstance(params, dict):
        return None

    if connector_key == "home_assistant" and operation == "call_service":
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

    if connector_key == "webhook" and operation == "trigger":
        event = " ".join(str(params.get("event") or "").split()).strip()
        payload = params.get("payload")
        if not event:
            return None
        if payload is not None and not isinstance(payload, dict):
            return None
        normalized = {
            "name": "connector.invoke",
            "connector": connector_key,
            "operation": operation,
            "params": {"event": event},
        }
        if isinstance(payload, dict) and payload:
            normalized["params"]["payload"] = payload
        return normalized

    return None


def execute_connector_action(user, action: dict) -> None:
    connector_key = action.get("connector")
    operation = action.get("operation")
    params = action.get("params")
    if connector_key == "home_assistant" and operation == "call_service" and isinstance(params, dict):
        _execute_home_assistant_service(user, params)
        return
    if connector_key == "webhook" and operation == "trigger" and isinstance(params, dict):
        _execute_webhook_trigger(user, params)
        return
    raise RuntimeError("Action de connecteur invalide.")


def connector_test_contexts(user) -> list[dict]:
    contexts: list[dict] = []
    for definition in connector_definitions():
        if not is_connector_configured(user, definition.key):
            continue
        error = None
        extra: dict = {}
        if definition.key == "home_assistant":
            try:
                extra["entities"] = _home_assistant_entities(user)
            except RuntimeError as exc:
                error = str(exc)
                extra["entities"] = []
        contexts.append(
            {
                "key": definition.key,
                "label": definition.label,
                "description": definition.test_form.description if definition.test_form else definition.description,
                "test_form": {
                    "fields": [asdict(field) for field in definition.test_form.fields]
                }
                if definition.test_form
                else None,
                "error": error,
                **extra,
            }
        )
    return contexts


def _normalize_url(url: str | None) -> str:
    normalized = " ".join(str(url or "").split()).strip()
    if not normalized:
        return ""
    if not normalized.startswith(("http://", "https://")):
        normalized = f"http://{normalized}"
    return normalized.rstrip("/")


def _connector_http_request(
    *,
    url: str,
    token: str | None = None,
    method: str = "POST",
    payload: dict | None = None,
    timeout: int = 10,
):
    headers = {"Accept": "application/json"}
    body = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request_object = urllib_request.Request(
        url,
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
        raise RuntimeError(f"Le connecteur a répondu en erreur: {message}") from exc
    except urllib_error.URLError as exc:
        raise RuntimeError(f"Impossible de joindre le connecteur: {exc.reason}") from exc
    if not raw_body:
        return None
    try:
        return json.loads(raw_body)
    except json.JSONDecodeError:
        return raw_body


def _home_assistant_entities(user, *, limit: int = 60) -> list[dict]:
    config = get_user_connector_config(user, "home_assistant")
    payload = _connector_http_request(
        url=f"{_normalize_url(config.get('base_url'))}/api/states",
        token=str(config.get("token") or "").strip(),
        method="GET",
    )
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
    config = get_user_connector_config(user, "home_assistant")
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
    _connector_http_request(
        url=f"{_normalize_url(config.get('base_url'))}/api/services/{domain}/{service}",
        token=str(config.get("token") or "").strip(),
        payload=payload,
    )


def _execute_webhook_trigger(user, params: dict) -> None:
    config = get_user_connector_config(user, "webhook")
    endpoint_url = _normalize_url(config.get("endpoint_url"))
    token = str(config.get("token") or "").strip()
    event = str(params.get("event") or "").strip()
    payload = params.get("payload")
    if not endpoint_url or not event:
        raise RuntimeError("Action webhook invalide.")
    if payload is not None and not isinstance(payload, dict):
        raise RuntimeError("Le payload webhook doit etre un objet JSON.")
    request_payload = {"event": event, "payload": payload or {}}
    _connector_http_request(url=endpoint_url, token=token, payload=request_payload)
