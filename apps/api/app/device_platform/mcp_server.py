from __future__ import annotations

import json
from pathlib import Path

import anyio
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Resource, Tool

from ..config import load_gateway_settings
from .models import (
    DeviceExecutionRequest,
    DeviceExecutionResult,
    DeviceModelListResponse,
    DeviceModelResponse,
    DeviceProbeRequest,
    DeviceProbeResult,
)
from .service import create_device_platform_service

SERVER_NAME = "nabaztag-device-platform"
ARCHITECTURE_RESOURCE_URI = "nabaztag://device-platform/architecture"
MODEL_LIST_RESOURCE_URI = "nabaztag://device-platform/models"
ARCHITECTURE_DOC_PATH = Path(__file__).resolve().parents[4] / "docs" / "device-platform-architecture.md"


def build_server() -> Server:
    server = Server(SERVER_NAME)
    service = create_device_platform_service(load_gateway_settings())

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="list_device_models",
                description=(
                    "List the standardized device models supported by the new device-platform layer, "
                    "including planned and implemented rabbit families."
                ),
                inputSchema={"type": "object", "properties": {}, "additionalProperties": False},
                outputSchema=DeviceModelListResponse.model_json_schema(),
            ),
            Tool(
                name="get_device_model",
                description=(
                    "Return the capability descriptor for one device model, including primitive support "
                    "status and documentation references."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "model_key": {
                            "type": "string",
                            "pattern": "^[a-z0-9-]+$",
                            "description": "Model key such as `nabaztag-tag`, `nabaztag-v1` or `karotz`.",
                        }
                    },
                    "required": ["model_key"],
                    "additionalProperties": False,
                },
                outputSchema=DeviceModelResponse.model_json_schema(),
            ),
            Tool(
                name="probe_device",
                description=(
                    "Probe a physical rabbit target through the adapter selected by `model_key`, without "
                    "requiring the higher-level rabbit registry."
                ),
                inputSchema=DeviceProbeRequest.model_json_schema(),
                outputSchema=DeviceProbeResult.model_json_schema(),
            ),
            Tool(
                name="execute_device_primitive",
                description=(
                    "Execute one standardized primitive directly against a device target. This is the "
                    "transport-neutral command surface shared by the API and MCP layers."
                ),
                inputSchema=DeviceExecutionRequest.model_json_schema(),
                outputSchema=DeviceExecutionResult.model_json_schema(),
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> dict:
        if name == "list_device_models":
            return DeviceModelListResponse(models=service.list_models()).model_dump(mode="json")
        if name == "get_device_model":
            model_key = arguments.get("model_key")
            return DeviceModelResponse(model=service.get_model(model_key)).model_dump(mode="json")
        if name == "probe_device":
            payload = DeviceProbeRequest.model_validate(arguments)
            return service.probe(payload).model_dump(mode="json")
        if name == "execute_device_primitive":
            payload = DeviceExecutionRequest.model_validate(arguments)
            return service.execute(payload).model_dump(mode="json")
        raise ValueError(f"Unknown MCP tool `{name}`")

    @server.list_resources()
    async def list_resources() -> list[Resource]:
        resources = [
            Resource(
                name="Device Platform Architecture",
                uri=ARCHITECTURE_RESOURCE_URI,
                description=(
                    "Markdown architecture note describing the standardized primitive layer, the adapter "
                    "catalog and the API/MCP surfaces."
                ),
                mimeType="text/markdown",
            ),
            Resource(
                name="Device Platform Model Catalog",
                uri=MODEL_LIST_RESOURCE_URI,
                description="JSON descriptor catalog for all known rabbit families.",
                mimeType="application/json",
            ),
        ]
        for descriptor in service.list_models():
            resources.append(
                Resource(
                    name=f"Device Model {descriptor.label}",
                    uri=f"nabaztag://device-platform/models/{descriptor.key}",
                    description=f"JSON capability descriptor for {descriptor.label}.",
                    mimeType="application/json",
                )
            )
        return resources

    @server.read_resource()
    async def read_resource(uri) -> str:
        uri_text = str(uri)
        if uri_text == ARCHITECTURE_RESOURCE_URI:
            return ARCHITECTURE_DOC_PATH.read_text(encoding="utf-8")
        if uri_text == MODEL_LIST_RESOURCE_URI:
            return json.dumps(
                DeviceModelListResponse(models=service.list_models()).model_dump(mode="json"),
                indent=2,
            )
        model_prefix = "nabaztag://device-platform/models/"
        if uri_text.startswith(model_prefix):
            model_key = uri_text.removeprefix(model_prefix)
            return json.dumps(
                DeviceModelResponse(model=service.get_model(model_key)).model_dump(mode="json"),
                indent=2,
            )
        raise ValueError(f"Unknown MCP resource `{uri_text}`")

    return server


async def _serve_stdio() -> None:
    server = build_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main() -> None:
    anyio.run(_serve_stdio)


if __name__ == "__main__":
    main()
