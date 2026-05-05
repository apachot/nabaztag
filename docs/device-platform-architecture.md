# Device Platform Architecture

## Intent

The historical API in `apps/api/app/` is still centered on a logical `rabbit` aggregate. That is useful for the portal, but it mixes two responsibilities:

- a user-facing rabbit identity stored by the platform
- the hardware-specific transport contract needed to talk to a concrete device family

The new `device_platform` layer separates those concerns. It introduces a stable, transport-neutral primitive contract that can target a `Nabaztag v1`, a `Nabaztag:tag` or a `Karotz` independently.

## Layering

The architecture is split into three layers.

### 1. Product and orchestration layer

This remains the current portal and rabbit-centric API. It owns:

- users, rabbit records and serial attachment
- conversations and high-level behavior
- scheduling and command orchestration

This layer should not encode device-specific transport details.

### 2. Device platform layer

This is the new contract introduced in `apps/api/app/device_platform/`. It owns:

- the public catalog of supported device models
- the standardized primitive vocabulary
- the capability matrix of each model
- the API and MCP surfaces

This layer is intentionally explicit about what is supported, partially supported, planned or unsupported.

### 3. Transport adapter layer

Each device family gets its own adapter implementation. An adapter:

- receives a standardized primitive request
- validates whether the primitive is supported by that model
- translates the request to the underlying transport
- normalizes the returned state and errors

Adapters must stay thin. They translate and normalize; they do not own product rules.

## Standardized primitive contract

The first contract is intentionally small and capability-oriented:

- lifecycle: `connect`, `disconnect`, `sync`, `sleep`, `wakeup`
- motion: `ears.move`
- light: `led.set`
- audio output: `audio.play`
- audio capture: `audio.recording.start`, `audio.recording.stop`
- video capture: `video.snapshot`, `video.stream.start`, `video.stream.stop`

The important design rule is that unsupported capabilities stay public and explicit. We do not hide missing primitives behind silent no-ops or family-specific behavior.

## Capability model

Each device model is published through a `DeviceModelDescriptor`:

- stable `model_key`
- `family`
- implementation status
- transport summary
- API/MCP availability
- per-primitive support descriptors with limitations

This allows the portal, the CLI, external automations and MCP clients to discover what a specific hardware family can really do before calling it.

## Initial device matrix

### Nabaztag:tag

First concrete implementation. It uses the already-documented `nabd` JSONL protocol and is the reference adapter for the new layer.

- lifecycle primitives: implemented
- ear movement: implemented
- LED control: partially implemented through `left`, `center`, `right`
- audio playback: implemented
- audio recording: explicitly unsupported in this first adapter
- video: unsupported

### Nabaztag v1

Catalogued from day one as an independent family.

- microphone capture: explicitly unsupported in the public contract
- video: unsupported
- remaining primitives: reserved and documented as planned until the transport contract is stabilized

### Karotz

Catalogued from day one as an independent family.

- video snapshot and streaming primitives: reserved in the public contract
- audio recording: planned
- remaining primitives: reserved and documented as planned until the transport contract is stabilized

## API surface

The new REST surface is intentionally device-centric and independent from the rabbit registry:

- `GET /api/device-platform/models`
- `GET /api/device-platform/models/{model_key}`
- `POST /api/device-platform/probe`
- `POST /api/device-platform/execute`

The request payload always carries:

- a `model_key`
- a `target`
- an optional standardized primitive command

That makes the transport layer testable without first creating a rabbit record in the portal.

## MCP surface

The same models back a dedicated MCP server:

- tool: `list_device_models`
- tool: `get_device_model`
- tool: `probe_device`
- tool: `execute_device_primitive`

Resources expose the architecture note and the live model catalog. The REST and MCP surfaces share the same Pydantic models so the public contract is generated once and reused consistently.

After installing `apps/api`, the MCP server can be launched with:

- `python -m app.device_platform.mcp_server`
- or the installed console script `nabaztag-device-platform-mcp`

## Robustness rules

The first version of this layer follows a few hard rules:

- unsupported primitives raise explicit errors
- planned adapters are catalogued but not executable
- transport failures are distinct from capability errors
- the public descriptor is the source of truth for capability discovery
- adapters normalize state instead of leaking transport payloads into the upper product layer

## Migration strategy

The rabbit-centric API stays in place for existing consumers. The new device-platform layer evolves in parallel until:

1. all targeted families have their own adapters
2. the portal can bind a rabbit record to a `model_key` and a concrete target profile
3. higher-level orchestration can route commands through the standardized primitive contract instead of directly choosing a gateway implementation

This keeps the migration incremental while making the target architecture explicit now.
