from __future__ import annotations

import json
from urllib import error, request

from flask import current_app


class NabaztagApiError(RuntimeError):
    pass


def _api_request(path: str, *, method: str = "GET", payload: dict | None = None) -> dict | list:
    base_url = current_app.config["NABAZTAG_API_BASE_URL"].rstrip("/")
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = request.Request(
        f"{base_url}{path}",
        method=method,
        data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise NabaztagApiError(f"API error {exc.code}: {detail}") from exc
    except error.URLError as exc:
        raise NabaztagApiError(f"API unavailable: {exc.reason}") from exc


def create_remote_rabbit(name: str, slug: str) -> dict:
    return _api_request("/api/rabbits", method="POST", payload={"name": name, "slug": slug})


def set_remote_target(remote_id: str, host: str, port: int) -> dict:
    return _api_request(
        f"/api/rabbits/{remote_id}/target",
        method="PUT",
        payload={"host": host, "port": port},
    )


def prepare_remote_bootstrap(
    *,
    rabbit_id: str | None,
    home_wifi_ssid: str,
    home_wifi_password: str,
    server_base_url: str,
    bootstrap_host: str = "192.168.0.1",
    bootstrap_port: int = 80,
    rabbit_setup_ssid: str = "NabaztagXX",
) -> dict:
    return _api_request(
        "/api/bootstrap/submit",
        method="POST",
        payload={
            "rabbit_id": rabbit_id,
            "bootstrap_host": bootstrap_host,
            "bootstrap_port": bootstrap_port,
            "rabbit_setup_ssid": rabbit_setup_ssid,
            "home_wifi_ssid": home_wifi_ssid,
            "home_wifi_password": home_wifi_password,
            "server_base_url": server_base_url,
        },
    )


def fetch_remote_rabbit(remote_id: str) -> dict:
    return _api_request(f"/api/rabbits/{remote_id}")


def fetch_remote_events(remote_id: str) -> list[dict]:
    events = _api_request(f"/api/rabbits/{remote_id}/events")
    return events if isinstance(events, list) else []


def send_remote_action(remote_id: str, action: str, payload: dict | None = None) -> dict:
    suffix = {
        "connect": "/connect",
        "disconnect": "/disconnect",
        "sync": "/sync",
    }[action]
    return _api_request(
        f"/api/rabbits/{remote_id}{suffix}",
        method="POST",
        payload=payload or {},
    )
