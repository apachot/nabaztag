from __future__ import annotations

import json
import ssl
from pathlib import Path
from urllib import parse as urllib_parse
from urllib import request as urllib_request

import certifi


CONFIG_PATH = Path.home() / ".config" / "nabaztag-macos-client" / "config.json"


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
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    with urllib_request.urlopen(request_object, timeout=timeout, context=ssl_context) as response:
        raw = response.read().decode("utf-8")
    return json.loads(raw) if raw else {}
