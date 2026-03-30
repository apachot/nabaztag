# Nabaztag Control Surface

Monorepo for a modern Nabaztag control stack centered on a Flask portal, a FastAPI device API, and the legacy Violet-compatible endpoints needed by physical rabbits.

## Apps

- `apps/portal`: Flask portal for accounts, rabbit inventory, device control, conversation history, and AI features
- `apps/api`: FastAPI backend exposing rabbit state, commands, and event logs
- `apps/web`: legacy Next.js exploratory UI kept for reference

## Current Scope

The project now covers more than the initial MVP primitives.

Portal and rabbit features:

- account registration and login
- rabbit inventory and per-rabbit detail page
- device attach, sync, and remote state display
- ears, LEDs, and audio playback
- per-rabbit personality prompt
- per-rabbit Mistral LLM model selection
- per-rabbit Mistral Voxtral TTS voice selection
- generated rabbit performances with text, ears, and LEDs
- persisted conversation turns with aggressive pruning
- Violet-compatible recording upload endpoint and transcription pipeline

AI stack:

- Mistral chat completions for generated responses
- Mistral Voxtral TTS for speech synthesis
- structured JSON generation so the rabbit can express itself through speech, ears, and LEDs

## Run

### Portal

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ./apps/portal
export NABAZTAG_API_BASE_URL=http://localhost:8000
flask --app portal_app:create_app run --debug --port 5000
```

The Flask portal runs by default on `http://localhost:5000`.

### API

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ./apps/api
uvicorn app.main:app --reload --app-dir apps/api
```

### Legacy Web

```bash
npm install
npm run dev:web
```

## Gateway Drivers

The API can run with two gateway drivers:

- `simulated`: default, in-memory device behavior
- `protocol`: Nabaztag protocol adapter

Copy `apps/api/.env.example` to `apps/api/.env` and set:

```bash
NABAZTAG_GATEWAY_DRIVER=simulated
```

When `protocol` is selected, the API uses the protocol gateway for supported operations. Not every primitive is implemented by the underlying protocol layer yet, notably remote recording control.

The protocol layer is split into:

- `apps/api/app/protocol/client.py`: transport client entry point
- `apps/api/app/protocol/commands.py`: API primitive to protocol command mapping
- `apps/api/app/protocol/events.py`: protocol event to rabbit state mapping

Current protocol findings are documented in `docs/protocol-notes.md`.

## Protocol Smoke Test

1. Copy `apps/api/.env.example` to `apps/api/.env`
2. Set:

```bash
NABAZTAG_GATEWAY_DRIVER=protocol
NABAZTAG_GATEWAY_HOST=<ip-or-host-of-nabd>
NABAZTAG_GATEWAY_PORT=10543
```

`NABAZTAG_GATEWAY_HOST` and `NABAZTAG_GATEWAY_PORT` act as the default target. The web assistant can save a dedicated target per rabbit after detection.

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

## Production Domain

The production public entrypoints are:

- `https://nabaztag.org/`: Flask portal
- `https://nabaztag.org/api/`: FastAPI API
- `https://nabaztag.org/vl`: Violet Platform HTTP root
- `https://nabaztag.org/vl/locate.jsp`: initial Nabaztag locate response
- `5222/TCP` on `nabaztag.org`: XMPP listener

Legacy routes under `https://dev.emotia.com/nabaztag/` are redirected to `https://nabaztag.org/`.

## systemd

Production service unit files are versioned in:

- `deploy/systemd/nabaztag-portal.service`
- `deploy/systemd/nabaztag-xmpp.service`

To install them on the Debian server:

```bash
sudo cp deploy/systemd/nabaztag-portal.service /etc/systemd/system/
sudo cp deploy/systemd/nabaztag-xmpp.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now nabaztag-portal.service
sudo systemctl enable --now nabaztag-xmpp.service
```
