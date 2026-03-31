from __future__ import annotations

import asyncio
import base64
import binascii
import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import timedelta

from . import create_app
from .device_protocol import (
    EncodedPacket,
    build_audio_packet,
    build_body_led_packet,
    build_ears_packet,
    build_init_packet,
    build_nose_or_bottom_packet,
)
from .models import DeviceObservation, RabbitDeviceCommand, RabbitEventLog, RabbitRecording, utc_now
from .extensions import db

LOG = logging.getLogger("nabaztag.xmpp")
LED_REFRESH_INTERVAL = timedelta(seconds=2)

SASL_NS = "urn:ietf:params:xml:ns:xmpp-sasl"
STREAM_NS = "http://etherx.jabber.org/streams"
CLIENT_NS = "jabber:client"
BIND_NS = "urn:ietf:params:xml:ns:xmpp-bind"
SESSION_NS = "urn:ietf:params:xml:ns:xmpp-session"
APP = create_app()
ACTIVE_SESSIONS: dict[str, "XmppSession"] = {}


def _age_exceeds(value, threshold: timedelta) -> bool:
    if value is None:
        return True
    try:
        now = utc_now()
        candidate = value
        if getattr(candidate, "tzinfo", None) is None:
            candidate = candidate.replace(tzinfo=now.tzinfo)
        return now - candidate >= threshold
    except Exception:
        return True


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


def _xmpp_domain() -> str:
    return _env("NABAZTAG_VL_XMPP_SERVER", "nabaztag.org")


def _stream_open(domain: str, stream_id: str) -> str:
    return (
        "<?xml version='1.0'?>"
        f"<stream:stream xmlns='{CLIENT_NS}' xmlns:stream='{STREAM_NS}' "
        f"id='{stream_id}' from='{domain}' version='1.0' xml:lang='en'>"
    )


def _auth_features() -> str:
    return (
        f"<stream:features><mechanisms xmlns='{SASL_NS}'>"
        "<mechanism>DIGEST-MD5</mechanism><mechanism>PLAIN</mechanism>"
        "</mechanisms><register xmlns='http://violet.net/features/violet-register'/>"
        "</stream:features>"
    )


def _post_auth_features() -> str:
    return (
        f"<stream:features><bind xmlns='{BIND_NS}'><required/></bind>"
        f"<unbind xmlns='{BIND_NS}'/><session xmlns='{SESSION_NS}'/>"
        "</stream:features>"
    )


def _extract_resource(stanza: str) -> str | None:
    match = re.search(r"<resource>([^<]+)</resource>", stanza)
    return match.group(1) if match else None


def _extract_attr(stanza: str, attr: str) -> str | None:
    match = re.search(rf"{attr}=['\"]([^'\"]+)['\"]", stanza)
    return match.group(1) if match else None


def _extract_tag_value(stanza: str, tag: str) -> str | None:
    match = re.search(rf"<{tag}>([^<]+)</{tag}>", stanza)
    return match.group(1) if match else None


def _extract_jid_node(stanza: str, attr: str = "from") -> str | None:
    value = _extract_attr(stanza, attr)
    if not value or "@" not in value:
        return None
    return value.split("@", 1)[0]


def _extract_complete_stanzas(buffer: str) -> tuple[list[str], str]:
    stanzas: list[str] = []
    remaining = buffer

    while remaining:
        remaining = remaining.lstrip()
        if not remaining:
            break

        if remaining.startswith(" "):
            stanzas.append(" ")
            remaining = remaining[1:]
            continue

        candidates = (
            ("<?xml", "?>"),
            ("<stream:stream", ">"),
            ("<auth", "/>"),
            ("<response", "</response>"),
            ("<challenge", "</challenge>"),
            ("<success", "/>"),
            ("<iq", "</iq>"),
            ("<presence", "</presence>"),
            ("<message", "</message>"),
        )

        matched = False
        for prefix, terminator in candidates:
            if not remaining.startswith(prefix):
                continue
            end_index = remaining.find(terminator)
            if end_index == -1:
                return stanzas, remaining
            stanza = remaining[: end_index + len(terminator)]
            stanzas.append(stanza)
            remaining = remaining[end_index + len(terminator):]
            matched = True
            break

        if matched:
            continue

        next_start = remaining.find("<", 1)
        if next_start == -1:
            return stanzas, remaining
        remaining = remaining[next_start:]

    return stanzas, remaining


def _reply_iq(request: str, iq_type: str, content: str | None = None) -> str:
    iq_id = _extract_attr(request, "id") or "iq-1"
    from_attr = _extract_attr(request, "from")
    to_attr = _extract_attr(request, "to")
    attributes = [f"id='{iq_id}'", f"type='{iq_type}'"]
    if to_attr:
        attributes.append(f"from='{to_attr}'")
    if from_attr:
        attributes.append(f"to='{from_attr}'")
    head = f"<iq {' '.join(attributes)}"
    if content is None:
        return head + "/>"
    return head + f">{content}</iq>"


@dataclass
class XmppSession:
    writer: asyncio.StreamWriter
    peer: str
    domain: str
    auth_step: int = 0
    username: str | None = None
    resource: str | None = None
    buffer: str = field(default_factory=str)
    raw_mode: bool = False

    async def send_packet(self, packet: EncodedPacket) -> None:
        if not self.username or not self.resource:
            raise RuntimeError("Rabbit session is not ready yet")
        encoded = base64.b64encode(packet.payload).decode("ascii")
        stanza = (
            f"<message from='net.openjabnab.platform@{self.domain}/services' "
            f"to='{self.username}@{self.domain}/{self.resource}' id='py-{int(asyncio.get_running_loop().time() * 1000)}'>"
            f"<packet xmlns='violet:packet' format='1.0' ttl='604800'>{encoded}</packet>"
            "</message>"
        )
        await self.write(stanza)

    async def write(self, data: str) -> None:
        LOG.info("xmpp -> %s %s", self.peer, data[:400])
        self.writer.write(data.encode("utf-8"))
        await self.writer.drain()

    async def handle_chunk(self, chunk: str) -> None:
        LOG.info("xmpp <- %s %s", self.peer, chunk[:400])

        if self.auth_step == 0 and chunk.startswith("<?xml"):
            await self.write(_stream_open(self.domain, "nabaztag-auth"))
            await self.write(_auth_features())
            self.auth_step = 1
            return

        if self.auth_step == 1 and "violet:iq:register" in chunk and "type='get'" in chunk:
            iq_id = _extract_attr(chunk, "id") or "1"
            await self.write(
                f"<iq type='result' id='{iq_id}' from='{self.domain}'>"
                "<query xmlns='violet:iq:register'>"
                "<instructions>Choose a username and password to register with this server</instructions>"
                "<username/><password/></query></iq>"
            )
            self.auth_step = 100
            return

        if self.auth_step == 100 and "violet:iq:register" in chunk and "type='set'" in chunk:
            self.username = _extract_tag_value(chunk, "username") or self.username
            iq_id = _extract_attr(chunk, "id") or "2"
            query_match = re.search(r"(<query xmlns=\"violet:iq:register\">.*</query>)", chunk)
            query = query_match.group(1) if query_match else "<query xmlns='violet:iq:register'/>"
            await self.write(f"<iq type='result' id='{iq_id}'>{query}</iq>")
            self.auth_step = 1
            return

        if self.auth_step == 1 and f"mechanism='DIGEST-MD5'" in chunk:
            challenge = 'nonce="123456789",qop="auth",charset=utf-8,algorithm=md5-sess'
            encoded = base64.b64encode(challenge.encode("utf-8")).decode("ascii")
            await self.write(f"<challenge xmlns='{SASL_NS}'>{encoded}</challenge>")
            self.auth_step = 2
            return

        if self.auth_step == 2 and "<response" in chunk:
            decoded = ""
            match = re.search(r"<response[^>]*>(.*)</response>", chunk)
            if match:
                try:
                    decoded = base64.b64decode(match.group(1)).decode("utf-8", errors="ignore")
                except Exception:
                    decoded = ""
            username_match = re.search(r'username="([^"]+)"', decoded)
            if username_match:
                self.username = username_match.group(1)
            await self.write(f"<success xmlns='{SASL_NS}'/>")
            self.auth_step = 4
            return

        if self.auth_step == 4 and chunk.startswith("<?xml"):
            await self.write(_stream_open(self.domain, "nabaztag-bind"))
            await self.write(_post_auth_features())
            self.auth_step = 10
            return

        if self.auth_step >= 10 and "<bind" in chunk and "<resource>" in chunk:
            if not self.username:
                self.username = _extract_jid_node(chunk, "from") or self.username
            resource = _extract_resource(chunk) or "idle"
            self.resource = resource
            if self.username:
                ACTIVE_SESSIONS[self.username.lower()] = self
            jid = f"{self.username or 'anonymous'}@{self.domain}/{resource}"
            await self.write(_reply_iq(chunk, "result", f"<bind xmlns='{BIND_NS}'><jid>{jid}</jid></bind>"))
            return

        if self.auth_step >= 10 and f"<session xmlns='{SESSION_NS}'/>" in chunk:
            if not self.username:
                self.username = _extract_jid_node(chunk, "from") or self.username
                if self.username and self.resource:
                    ACTIVE_SESSIONS[self.username.lower()] = self
            await self.write(_reply_iq(chunk, "result", f"<session xmlns='{SESSION_NS}'/>"))
            return

        if self.auth_step >= 10 and 'xmlns="jabber:iq:version"' in chunk:
            return

        if self.auth_step >= 10 and 'xmlns="violet:iq:sources"' in chunk:
            status = base64.b64encode(build_init_packet()).decode("ascii")
            await self.write(
                _reply_iq(
                    chunk,
                    "result",
                    f"<query xmlns='violet:iq:sources'><packet xmlns='violet:packet' format='1.0' ttl='604800'>{status}</packet></query>",
                )
            )
            return

        if self.auth_step >= 10 and "<unbind" in chunk and "<resource>" in chunk:
            await self.write(_reply_iq(chunk, "result", None))
            return

        if self.auth_step >= 10 and chunk.startswith("<presence"):
            from_attr = _extract_attr(chunk, "from") or ""
            stanza_id = _extract_attr(chunk, "id") or "presence-1"
            await self.write(f"<presence from='{from_attr}' to='{from_attr}' id='{stanza_id}'/>")
            return

        if chunk == " ":
            return

        if "<message" in chunk and "<button" in chunk:
            click_value = _extract_tag_value(chunk, "clic")
            if self.username and click_value:
                _record_device_event(
                    self.username,
                    "rabbit.button",
                    {
                        "click": int(click_value),
                        "peer": self.peer,
                        "resource": self.resource,
                    },
                )
            return

        if "<message" in chunk and "<ears" in chunk:
            left = _extract_tag_value(chunk, "left")
            right = _extract_tag_value(chunk, "right")
            if self.username and left is not None and right is not None:
                _record_device_event(
                    self.username,
                    "rabbit.ears.moved",
                    {
                        "left": int(left),
                        "right": int(right),
                        "peer": self.peer,
                        "resource": self.resource,
                    },
                )
            return

        LOG.warning("unhandled xmpp stanza from %s: %s", self.peer, chunk[:400])


async def _handle_connection(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    peer_info = writer.get_extra_info("peername")
    peer = f"{peer_info[0]}:{peer_info[1]}" if peer_info else "unknown"
    session = XmppSession(writer=writer, peer=peer, domain=_xmpp_domain())
    LOG.info("xmpp connect %s", peer)
    try:
        while not reader.at_eof():
            data = await reader.read(4096)
            if not data:
                break
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                text = ""

            printable_ratio = 0.0
            if data:
                printable_ratio = sum(32 <= byte <= 126 or byte in (9, 10, 13) for byte in data) / len(data)

            if text and printable_ratio > 0.8:
                session.buffer += text
                stanzas, session.buffer = _extract_complete_stanzas(session.buffer)
                for stanza in stanzas:
                    stripped = stanza.strip()
                    if stripped:
                        await session.handle_chunk(stripped)
            else:
                hex_preview = binascii.hexlify(data[:64]).decode("ascii")
                LOG.warning(
                    "xmpp non-text payload from %s bytes=%s hex=%s",
                    peer,
                    len(data),
                    hex_preview,
                )
    except Exception:
        LOG.exception("xmpp connection failure %s", peer)
    finally:
        if session.username:
            ACTIVE_SESSIONS.pop(session.username.lower(), None)
        LOG.info("xmpp disconnect %s", peer)
        writer.close()
        await writer.wait_closed()


def _record_device_event(serial: str, event_type: str, payload: dict) -> None:
    with APP.app_context():
        normalized = serial.lower()
        observation = DeviceObservation.query.filter_by(serial=normalized).first()
        rabbit_id = observation.rabbit_id if observation else None
        if observation is not None:
            observation.last_seen_at = utc_now()
            observation.last_path = f"xmpp:{event_type}"
            db.session.add(observation)
        if rabbit_id is not None:
            db.session.add(
                RabbitEventLog(
                    rabbit_id=rabbit_id,
                    source="device",
                    event_type=event_type,
                    payload=json.dumps(payload),
                )
            )
        db.session.commit()

def _build_packet_for_command(command: RabbitDeviceCommand) -> EncodedPacket:
    payload = json.loads(command.payload or "{}")
    if command.command_type == "audio":
        return build_audio_packet(payload["url"])
    if command.command_type == "audio_stop":
        return build_audio_packet(payload["url"])
    if command.command_type == "ears":
        return build_ears_packet(int(payload["left"]), int(payload["right"]))
    if command.command_type == "led":
        target = payload["target"]
        color = payload["color"]
        preset = payload.get("preset")
        if target in {"nose", "bottom"}:
            return build_nose_or_bottom_packet(target, color, preset)
        if target in {"left", "center", "right"}:
            return build_body_led_packet(target, color)
    raise RuntimeError(f"Unsupported command type: {command.command_type}")


async def _dispatch_commands_once() -> None:
    with APP.app_context():
        queued = (
            RabbitDeviceCommand.query.filter_by(status="queued")
            .order_by(RabbitDeviceCommand.created_at.asc())
            .limit(50)
            .all()
        )

    for command in queued:
        session = ACTIVE_SESSIONS.get(command.serial.lower())
        if session is None or not session.resource:
            continue
        try:
            packet = _build_packet_for_command(command)
            await session.send_packet(packet)
            with APP.app_context():
                current = db.session.get(RabbitDeviceCommand, command.id)
                if current is None:
                    continue
                current.status = "sent"
                current.sent_at = utc_now()
                db.session.add(current)
                db.session.add(
                    RabbitEventLog(
                        rabbit_id=current.rabbit_id,
                        source="device",
                        event_type=f"rabbit.command.{current.command_type}.sent",
                        payload=json.dumps({"serial": current.serial, "description": packet.description}),
                    )
                )
                db.session.commit()
        except Exception as exc:
            LOG.exception("command dispatch failure id=%s", command.id)
            with APP.app_context():
                current = db.session.get(RabbitDeviceCommand, command.id)
                if current is None:
                    continue
                current.status = "failed"
                current.error = str(exc)
                db.session.add(current)
                db.session.add(
                    RabbitEventLog(
                        rabbit_id=current.rabbit_id,
                        source="device",
                        event_type=f"rabbit.command.{current.command_type}.failed",
                        payload=json.dumps({"serial": current.serial, "error": str(exc)}),
                        level="error",
                    )
                )
                db.session.commit()

    await _refresh_sticky_leds()


async def _refresh_sticky_leds() -> None:
    with APP.app_context():
        led_commands = (
            RabbitDeviceCommand.query.filter_by(command_type="led")
            .order_by(RabbitDeviceCommand.created_at.desc())
            .all()
        )

    latest_by_target: dict[tuple[str, str], RabbitDeviceCommand] = {}
    for command in led_commands:
        try:
            payload = json.loads(command.payload or "{}")
        except json.JSONDecodeError:
            continue
        target = str(payload.get("target") or "")
        if not target:
            continue
        key = (command.serial.lower(), target)
        if key not in latest_by_target:
            latest_by_target[key] = command

    commands_to_refresh: list[RabbitDeviceCommand] = []
    for command in latest_by_target.values():
        try:
            payload = json.loads(command.payload or "{}")
        except json.JSONDecodeError:
            continue
        target = str(payload.get("target") or "")
        # Body LED choreographies force the rabbit into a busy state. Do not
        # refresh them periodically or they block later commands.
        if target in {"left", "center", "right"}:
            continue
        color = str(payload.get("color") or "").lower()
        if command.status != "sent" or color == "#000000":
            continue
        if not _age_exceeds(command.sent_at, LED_REFRESH_INTERVAL):
            continue
        commands_to_refresh.append(command)

    for command in commands_to_refresh:
        session = ACTIVE_SESSIONS.get(command.serial.lower())
        if session is None or not session.resource:
            continue

        try:
            packet = _build_packet_for_command(command)
            await session.send_packet(packet)
            with APP.app_context():
                current = db.session.get(RabbitDeviceCommand, command.id)
                if current is None:
                    continue
                current.sent_at = utc_now()
                db.session.add(current)
                db.session.commit()
        except Exception:
            LOG.exception("sticky led refresh failure id=%s", command.id)


async def _dispatch_loop() -> None:
    while True:
        try:
            await _dispatch_commands_once()
        except Exception:
            LOG.exception("command dispatcher failure")
        await asyncio.sleep(1.0)


async def _run() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    host = _env("NABAZTAG_XMPP_BIND_HOST", "0.0.0.0")
    port = int(_env("NABAZTAG_XMPP_BIND_PORT", "5222"))
    server = await asyncio.start_server(_handle_connection, host, port)
    LOG.info("xmpp listener ready on %s:%s for domain %s", host, port, _xmpp_domain())
    asyncio.create_task(_dispatch_loop())
    async with server:
        await server.serve_forever()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
