from __future__ import annotations

import os
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .dependencies import create_service
from .config import load_gateway_settings
from .models import (
    AudioCommand,
    BootstrapConfigRequest,
    BootstrapConfigResult,
    ConnectionCommand,
    DiscoveryProbeRequest,
    DiscoveryProbeResult,
    EarsCommand,
    LedCommand,
    Rabbit,
    RabbitCreate,
    RabbitDeviceLink,
    RabbitSummary,
    RabbitSync,
    RabbitTargetUpdate,
    RecordingStartCommand,
    RecordingStopCommand,
)
from .protocol.client import ProtocolClient
from .settings import GatewayError

service = create_service()


def _build_violet_platform_value(server_base_url: str) -> str:
    normalized = server_base_url.strip().rstrip("/")
    parsed = urlparse(normalized if "://" in normalized else f"https://{normalized}")
    host = parsed.netloc or parsed.path
    return f"{host.rstrip('/')}/vl"

app = FastAPI(
    title="Nabaztag API",
    version="0.1.0",
    root_path=os.getenv("NABAZTAG_API_ROOT_PATH", ""),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": "nabaztag-api",
        "status": "ok",
        "docs": "/docs",
        "health": "/health",
    }


@app.post("/api/bootstrap/submit", response_model=BootstrapConfigResult)
def submit_bootstrap_config(payload: BootstrapConfigRequest) -> BootstrapConfigResult:
    base_url = payload.server_base_url.rstrip("/")
    violet_platform = _build_violet_platform_value(base_url)
    bootstrap_url = f"http://{payload.bootstrap_host}:{payload.bootstrap_port}/"
    return BootstrapConfigResult(
        submitted=False,
        bootstrap_url=bootstrap_url,
        violet_platform=violet_platform,
        message=(
            "Bootstrap workflow prepared. The local Nabaztag provisioning protocol still needs "
            "to be implemented, but the expected target and server values are now fixed."
        ),
        next_steps=[
            "Connect your computer to the rabbit Wi-Fi network.",
            f"Open {bootstrap_url} or talk to its local provisioning API.",
            f"Set the Violet Platform field to {violet_platform}.",
            "Apply the Wi-Fi settings and wait for the rabbit to reboot on your home network.",
        ],
    )


@app.post("/api/discovery/probe", response_model=DiscoveryProbeResult)
def probe_nabaztag(payload: DiscoveryProbeRequest) -> DiscoveryProbeResult:
    settings = load_gateway_settings()
    client = ProtocolClient(settings)
    return client.probe(
        host=payload.host,
        port=payload.port,
        timeout_seconds=payload.timeout_seconds,
    )


@app.get("/api/rabbits", response_model=list[RabbitSummary])
def list_rabbits() -> list[RabbitSummary]:
    rabbits = service.list_rabbits()
    return [
        RabbitSummary(
            id=rabbit.id,
            slug=rabbit.slug,
            name=rabbit.name,
            connection_status=rabbit.connection_status,
            updated_at=rabbit.updated_at,
        )
        for rabbit in rabbits
    ]


@app.post("/api/rabbits", response_model=Rabbit)
def create_rabbit(payload: RabbitCreate) -> Rabbit:
    return service.create_rabbit(payload)


@app.get("/api/rabbits/{rabbit_id}", response_model=Rabbit)
def get_rabbit(rabbit_id: str) -> Rabbit:
    try:
        return service.get_rabbit(rabbit_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Rabbit not found") from exc


@app.put("/api/rabbits/{rabbit_id}/target", response_model=Rabbit)
def update_rabbit_target(rabbit_id: str, payload: RabbitTargetUpdate) -> Rabbit:
    try:
        return service.set_target(rabbit_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Rabbit not found") from exc


@app.post("/api/rabbits/{rabbit_id}/link-device", response_model=Rabbit)
def link_rabbit_device(rabbit_id: str, payload: RabbitDeviceLink) -> Rabbit:
    try:
        return service.link_device(rabbit_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Rabbit not found") from exc


@app.get("/api/rabbits/{rabbit_id}/events")
def list_events(rabbit_id: str) -> list[dict]:
    try:
        service.get_rabbit(rabbit_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Rabbit not found") from exc
    return [event.model_dump(mode="json") for event in service.list_events(rabbit_id)]


@app.get("/api/rabbits/{rabbit_id}/commands")
def list_commands(rabbit_id: str) -> list[dict]:
    try:
        service.get_rabbit(rabbit_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Rabbit not found") from exc
    return [command.model_dump(mode="json") for command in service.list_commands(rabbit_id)]


@app.post("/api/rabbits/{rabbit_id}/connect", response_model=RabbitSync)
def connect_rabbit(rabbit_id: str, payload: ConnectionCommand) -> RabbitSync:
    try:
        return service.connect(rabbit_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Rabbit not found") from exc


@app.post("/api/rabbits/{rabbit_id}/disconnect", response_model=RabbitSync)
def disconnect_rabbit(rabbit_id: str) -> RabbitSync:
    try:
        return service.disconnect(rabbit_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Rabbit not found") from exc


@app.post("/api/rabbits/{rabbit_id}/sync", response_model=RabbitSync)
def sync_rabbit(rabbit_id: str) -> RabbitSync:
    try:
        return service.sync(rabbit_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Rabbit not found") from exc


@app.post("/api/rabbits/{rabbit_id}/commands/led")
def apply_led(rabbit_id: str, payload: LedCommand) -> dict:
    try:
        command = service.apply_led(rabbit_id, payload)
        rabbit = service.get_rabbit(rabbit_id)
    except GatewayError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Rabbit not found") from exc
    return {"command": command.model_dump(mode="json"), "state": rabbit.state.model_dump()}


@app.post("/api/rabbits/{rabbit_id}/commands/ears")
def apply_ears(rabbit_id: str, payload: EarsCommand) -> dict:
    try:
        command = service.apply_ears(rabbit_id, payload)
        rabbit = service.get_rabbit(rabbit_id)
    except GatewayError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Rabbit not found") from exc
    return {"command": command.model_dump(mode="json"), "state": rabbit.state.model_dump()}


@app.post("/api/rabbits/{rabbit_id}/commands/audio")
def start_audio(rabbit_id: str, payload: AudioCommand) -> dict:
    try:
        command = service.start_audio(rabbit_id, payload)
        rabbit = service.get_rabbit(rabbit_id)
    except GatewayError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Rabbit not found") from exc
    return {"command": command.model_dump(mode="json"), "state": rabbit.state.model_dump()}


@app.post("/api/rabbits/{rabbit_id}/commands/recording/start")
def start_recording(rabbit_id: str, payload: RecordingStartCommand) -> dict:
    try:
        command = service.start_recording(rabbit_id, payload)
        rabbit = service.get_rabbit(rabbit_id)
    except GatewayError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Rabbit not found") from exc
    return {"command": command.model_dump(mode="json"), "state": rabbit.state.model_dump()}


@app.post("/api/rabbits/{rabbit_id}/commands/recording/stop")
def stop_recording(rabbit_id: str, payload: RecordingStopCommand) -> dict:
    try:
        command = service.stop_recording(rabbit_id, payload)
        rabbit = service.get_rabbit(rabbit_id)
    except GatewayError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Rabbit not found") from exc
    return {"command": command.model_dump(mode="json"), "state": rabbit.state.model_dump()}
