# Nabaztag Protocol Notes

Working target for the first real device adapter is the `pynab` `nabd` TCP protocol.

## Confirmed transport

- TCP server listening on port `10543`
- one JSON packet per line, terminated with CRLF
- the socket is local-only by default on the rabbit itself

## Confirmed packet families

- `state`: emitted by `nabd` on connection and on state changes
- `info`: updates the idle LED animation
- `ears`: updates idle ear positions
- `command`: plays audio and choreography sequences
- `mode`: switches between `idle` and `interactive`, optionally subscribing to events
- `wakeup` / `sleep`
- `response`: completion or protocol error for requests
- `button_event`, `ears_event`, `rfid_event`, `asr_event`

## Mapping to our API primitives

### Supported now in protocol mode

- gateway connect: open socket, wait for initial `state`, then send `mode`
- gateway sync: open socket and consume the initial `state`
- ears: map to packet `{"type":"ears", ...}`
- audio playback: map to packet `{"type":"command","sequence":[{"audio":[...]}]}`

### Partially supported

- LEDs: `info` only exposes `left`, `center`, `right` in idle mode
- richer LED control likely needs choreography payloads rather than a simple dedicated LED packet

### Not directly supported by documented `nabd` protocol

- raw microphone recording start/stop with audio file retrieval
- direct nose/bottom LED primitives as a first-class packet

## Consequence for the backend

The protocol gateway should treat:

- `left`, `center`, `right` LEDs as the first real hardware-compatible LED primitive
- `nose` and `bottom` as unsupported in `protocol` mode until a choreography-based path is specified
- recording as a separate future capability, not part of the first `nabd` adapter

## Current implementation status

Inference from the protocol documentation:

- the current backend now uses a real TCP JSONL client against `nabd`
- `connect`, `disconnect`, `sync`, `ears`, `info`, and `command` use the documented transport
- event subscriptions are not yet managed beyond simple mode switching
- long-running interactive sessions are not implemented yet; each API call opens a short-lived socket
