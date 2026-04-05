from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from urllib import parse as urllib_parse
from urllib import error as urllib_error
from urllib import request as urllib_request


CONFIG_PATH = Path.home() / ".config" / "nabaztag-local-bridge" / "config.json"
DEFAULT_CAPABILITIES = [
    {"name": "webhook.trigger", "description": "POST JSON vers un endpoint HTTP local ou distant"},
    {"name": "mqtt.publish", "description": "Publication MQTT locale si paho-mqtt est disponible"},
]


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text())
    except Exception:
        return {}


def save_config(config: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2, ensure_ascii=False))


def normalize_portal_base(portal: str) -> str:
    normalized = portal.strip().rstrip("/")
    parsed = urllib_parse.urlparse(normalized)
    host = (parsed.hostname or "").strip().lower()
    if parsed.scheme == "http" and host not in {"localhost", "127.0.0.1"}:
        parsed = parsed._replace(scheme="https")
        normalized = urllib_parse.urlunparse(parsed).rstrip("/")
    return normalized


def http_json(
    *,
    url: str,
    method: str = "GET",
    token: str | None = None,
    payload: dict | None = None,
    timeout: float = 30,
) -> dict:
    headers = {"Accept": "application/json"}
    body = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request_object = urllib_request.Request(url, data=body, headers=headers, method=method.upper())
    with urllib_request.urlopen(request_object, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
    return json.loads(raw) if raw else {}


def pair(args: argparse.Namespace) -> int:
    portal = normalize_portal_base(args.portal)
    capabilities = DEFAULT_CAPABILITIES
    response = http_json(
        url=f"{portal}/bridge-api/v1/pairing/claim",
        method="POST",
        payload={
            "pairing_token": args.pairing_token,
            "bridge_name": args.name,
            "capabilities": capabilities,
        },
    )
    if not response.get("ok"):
        print(response.get("message") or "Appairage impossible.", file=sys.stderr)
        return 1
    config = {
        "portal": portal,
        "bridge_token": response["bridge_token"],
        "bridge": response["bridge"],
    }
    save_config(config)
    print(f"Bridge appairé: {response['bridge']['name']}")
    print(f"Configuration sauvegardée dans {CONFIG_PATH}")
    return 0


def execute_webhook_trigger(params: dict) -> dict:
    endpoint_url = " ".join(str(params.get("endpoint_url") or "").split()).strip()
    payload = params.get("payload") if isinstance(params.get("payload"), dict) else {}
    token = str(params.get("token") or "").strip()
    if not endpoint_url:
        raise RuntimeError("endpoint_url obligatoire pour webhook.trigger")
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(payload).encode("utf-8")
    headers["Content-Type"] = "application/json"
    request_object = urllib_request.Request(endpoint_url, data=body, headers=headers, method="POST")
    try:
        with urllib_request.urlopen(request_object, timeout=20) as response:
            return {"status": response.status}
    except urllib_error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore").strip()
        raise RuntimeError(detail or f"HTTP {exc.code}") from exc
    except urllib_error.URLError as exc:
        raise RuntimeError(str(exc.reason)) from exc


def execute_mqtt_publish(params: dict) -> dict:
    try:
        from paho.mqtt.publish import single as mqtt_publish_single
    except Exception as exc:
        raise RuntimeError("paho-mqtt n'est pas installé localement") from exc

    host = " ".join(str(params.get("host") or "127.0.0.1").split()).strip()
    topic = " ".join(str(params.get("topic") or "").split()).strip()
    if not topic:
        raise RuntimeError("topic obligatoire pour mqtt.publish")
    payload = params.get("payload")
    if isinstance(payload, (dict, list)):
        payload_to_send = json.dumps(payload, ensure_ascii=False)
    elif payload is None:
        payload_to_send = ""
    else:
        payload_to_send = str(payload)
    port = int(params.get("port", 1883))
    qos = int(params.get("qos", 0))
    retain = bool(params.get("retain", False))
    auth = None
    username = str(params.get("username") or "").strip()
    password = str(params.get("password") or "").strip()
    if username:
        auth = {"username": username, "password": password}
    mqtt_publish_single(
        topic=topic,
        payload=payload_to_send,
        hostname=host,
        port=port,
        qos=qos,
        retain=retain,
        auth=auth,
    )
    return {"topic": topic, "host": host, "port": port}


def execute_command(command_payload: dict) -> dict:
    capability = " ".join(str(command_payload.get("capability") or "").split()).strip()
    action = " ".join(str(command_payload.get("action") or "").split()).strip()
    params = command_payload.get("params") if isinstance(command_payload.get("params"), dict) else {}
    if capability == "webhook.trigger" and action == "trigger":
        return execute_webhook_trigger(params)
    if capability == "mqtt.publish" and action == "publish":
        return execute_mqtt_publish(params)
    raise RuntimeError(f"Capacité non supportée: {capability}.{action}")


def run(args: argparse.Namespace) -> int:
    config = load_config()
    portal = normalize_portal_base(str(config.get("portal") or ""))
    token = str(config.get("bridge_token") or "").strip()
    if not portal or not token:
        print("Bridge non configuré. Lance d'abord la commande `pair`.", file=sys.stderr)
        return 1
    interval = max(1.0, float(args.interval))
    print(f"Bridge actif sur {portal}")
    while True:
        try:
            response = http_json(
                url=f"{portal}/bridge-api/v1/commands/next",
                method="GET",
                token=token,
            )
            command = response.get("command")
            if not command:
                time.sleep(interval)
                continue
            command_id = int(command["id"])
            try:
                result = execute_command(command.get("payload") or {})
                http_json(
                    url=f"{portal}/bridge-api/v1/commands/{command_id}/complete",
                    method="POST",
                    token=token,
                    payload={"status": "done", "result": result},
                )
                print(f"Commande {command_id} exécutée")
            except Exception as exc:
                http_json(
                    url=f"{portal}/bridge-api/v1/commands/{command_id}/complete",
                    method="POST",
                    token=token,
                    payload={"status": "failed", "error": str(exc)},
                )
                print(f"Commande {command_id} en échec: {exc}", file=sys.stderr)
        except Exception as exc:
            print(f"Erreur bridge: {exc}", file=sys.stderr)
            time.sleep(interval)


def main() -> int:
    parser = argparse.ArgumentParser(description="Nabaztag Local Bridge")
    subparsers = parser.add_subparsers(dest="command", required=True)

    pair_parser = subparsers.add_parser("pair", help="Appairer ce bridge avec le portail")
    pair_parser.add_argument("--portal", required=True, help="URL du portail Nabaztag, par ex. https://nabaztag.org")
    pair_parser.add_argument("--pairing-token", required=True, help="Code temporaire généré dans Mon compte")
    pair_parser.add_argument("--name", default="maison", help="Nom de ce bridge local")

    run_parser = subparsers.add_parser("run", help="Lancer la boucle de polling du bridge")
    run_parser.add_argument("--interval", type=float, default=3.0, help="Intervalle de polling en secondes")

    args = parser.parse_args()
    if args.command == "pair":
        return pair(args)
    if args.command == "run":
        return run(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
