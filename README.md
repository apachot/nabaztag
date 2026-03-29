# Nabaztag Control Surface

Monorepo for a first Nabaztag MVP:

- `apps/portal`: Flask portal for accounts, login, and rabbit inventory
- `apps/api`: FastAPI backend exposing rabbit state, commands, and event logs
- `apps/web`: legacy Next.js control surface kept as exploratory UI

## Scope

This first version validates the core primitives before any LLM integration:

- rabbit registration
- gateway attach, connect, disconnect, sync
- connection state and status
- LEDs
- ears
- audio playback
- recording lifecycle

## Run

### Portal

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ./apps/portal
export NABAZTAG_API_BASE_URL=http://localhost:8000
flask --app portal_app:create_app run --debug --port 5000
```

### Legacy Web

```bash
npm install
npm run dev:web
```

### API

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ./apps/api
uvicorn app.main:app --reload --app-dir apps/api
```

The Flask portal runs by default on `http://localhost:5000`.

## Gateway drivers

The API can run with two gateway drivers:

- `simulated`: default, in-memory device behavior
- `protocol`: reserved for the future Nabaztag protocol adapter

Copy `apps/api/.env.example` to `apps/api/.env` and set:

```bash
NABAZTAG_GATEWAY_DRIVER=simulated
```

When `protocol` is selected, the API boots with the protocol gateway skeleton but device
operations still return `501 Not Implemented` until the transport layer is wired.

The protocol layer is split into:

- `apps/api/app/protocol/client.py`: transport client entry point
- `apps/api/app/protocol/commands.py`: API primitive to protocol command mapping
- `apps/api/app/protocol/events.py`: protocol event to rabbit state mapping

Current protocol findings are documented in `docs/protocol-notes.md`.

## Protocol smoke test

1. Copy `apps/api/.env.example` to `apps/api/.env`
2. Set:

```bash
NABAZTAG_GATEWAY_DRIVER=protocol
NABAZTAG_GATEWAY_HOST=<ip-or-host-of-nabd>
NABAZTAG_GATEWAY_PORT=10543
```

`NABAZTAG_GATEWAY_HOST` and `NABAZTAG_GATEWAY_PORT` now act as the default target. The web
assistant can save a dedicated target per rabbit after detection.

3. Start the API:

```bash
uvicorn app.main:app --reload --app-dir apps/api
```

4. Run the HTTP smoke test:

```bash
bash scripts/smoke-test-protocol.sh
```

The smoke test exercises:

- rabbit creation
- connect
- sync
- ears
- audio
- one supported LED target: `center`
