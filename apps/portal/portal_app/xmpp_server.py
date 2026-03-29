from __future__ import annotations

import asyncio
import base64
import logging
import os
import re
from dataclasses import dataclass, field


LOG = logging.getLogger("nabaztag.xmpp")

SASL_NS = "urn:ietf:params:xml:ns:xmpp-sasl"
STREAM_NS = "http://etherx.jabber.org/streams"
CLIENT_NS = "jabber:client"
BIND_NS = "urn:ietf:params:xml:ns:xmpp-bind"
SESSION_NS = "urn:ietf:params:xml:ns:xmpp-session"


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


@dataclass
class XmppSession:
    writer: asyncio.StreamWriter
    peer: str
    domain: str
    auth_step: int = 0
    username: str | None = None
    resource: str | None = None
    buffer: str = field(default_factory=str)

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
            resource = _extract_resource(chunk) or "idle"
            self.resource = resource
            iq_id = _extract_attr(chunk, "id") or "bind-1"
            jid = f"{self.username or 'anonymous'}@{self.domain}/{resource}"
            await self.write(
                f"<iq type='result' id='{iq_id}'><bind xmlns='{BIND_NS}'><jid>{jid}</jid></bind></iq>"
            )
            return

        if self.auth_step >= 10 and f"<session xmlns='{SESSION_NS}'/>" in chunk:
            iq_id = _extract_attr(chunk, "id") or "session-1"
            await self.write(f"<iq type='result' id='{iq_id}'><session xmlns='{SESSION_NS}'/></iq>")
            return

        if self.auth_step >= 10 and 'xmlns="jabber:iq:version"' in chunk:
            return

        if self.auth_step >= 10 and 'xmlns="violet:iq:sources"' in chunk:
            iq_id = _extract_attr(chunk, "id") or "sources-1"
            await self.write(
                f"<iq type='result' id='{iq_id}'>"
                "<query xmlns='violet:iq:sources'><packet xmlns='violet:packet' format='1.0' ttl='604800'></packet></query>"
                "</iq>"
            )
            return

        if self.auth_step >= 10 and "<unbind" in chunk and "<resource>" in chunk:
            iq_id = _extract_attr(chunk, "id") or "unbind-1"
            await self.write(f"<iq type='result' id='{iq_id}'></iq>")
            return

        if self.auth_step >= 10 and chunk.startswith("<presence"):
            from_attr = _extract_attr(chunk, "from") or ""
            stanza_id = _extract_attr(chunk, "id") or "presence-1"
            await self.write(f"<presence from='{from_attr}' to='{from_attr}' id='{stanza_id}'/>")
            return

        if chunk == " ":
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
            text = data.decode("utf-8", errors="ignore").strip()
            if text:
                await session.handle_chunk(text)
    except Exception:
        LOG.exception("xmpp connection failure %s", peer)
    finally:
        LOG.info("xmpp disconnect %s", peer)
        writer.close()
        await writer.wait_closed()


async def _run() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    host = _env("NABAZTAG_XMPP_BIND_HOST", "0.0.0.0")
    port = int(_env("NABAZTAG_XMPP_BIND_PORT", "5222"))
    server = await asyncio.start_server(_handle_connection, host, port)
    LOG.info("xmpp listener ready on %s:%s for domain %s", host, port, _xmpp_domain())
    async with server:
        await server.serve_forever()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
