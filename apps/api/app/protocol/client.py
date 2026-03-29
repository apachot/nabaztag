from __future__ import annotations

from dataclasses import dataclass
import json
import socket
from uuid import uuid4

from ..models import ConnectionStatus, DiscoveryProbeResult
from ..settings import GatewayError, GatewaySettings
from .events import state_event_from_packet
from .types import ProtocolCommandEnvelope, ProtocolEventEnvelope, ProtocolResponseEnvelope


@dataclass
class ProtocolClient:
    settings: GatewaySettings

    def probe(self, host: str | None = None, port: int | None = None, timeout_seconds: float | None = None) -> DiscoveryProbeResult:
        target_host = host or self.settings.host
        target_port = port or self.settings.port
        probe_timeout = timeout_seconds or self.settings.connect_timeout_seconds
        probe_settings = GatewaySettings(
            driver="protocol",
            host=target_host,
            port=target_port,
            username=self.settings.username,
            password=self.settings.password,
            use_tls=self.settings.use_tls,
            connect_timeout_seconds=probe_timeout,
            read_timeout_seconds=probe_timeout,
        )

        try:
            with self._open_socket(probe_settings) as connection:
                packet = self._read_packet(connection, expected_type="state")
        except GatewayError as exc:
            return DiscoveryProbeResult(
                reachable=False,
                host=target_host,
                port=target_port,
                message=str(exc),
            )

        event = state_event_from_packet(packet)
        return DiscoveryProbeResult(
            reachable=True,
            host=target_host,
            port=target_port,
            state=packet.get("state"),
            connection_status=event.connection_status,
            packet=packet,
            message="nabd detected and initial state received",
        )

    def send(self, rabbit_slug: str, command: ProtocolCommandEnvelope) -> ProtocolEventEnvelope:
        return self.send_to(
            rabbit_slug=rabbit_slug,
            command=command,
            host=self.settings.host,
            port=self.settings.port,
        )

    def send_to(
        self,
        rabbit_slug: str,
        command: ProtocolCommandEnvelope,
        host: str,
        port: int,
    ) -> ProtocolEventEnvelope:
        if self.settings.driver != "protocol":
            raise GatewayError("Protocol client cannot be used when gateway driver is not `protocol`")

        packet = dict(command.payload)
        request_id = str(uuid4())
        packet["request_id"] = request_id
        runtime_settings = GatewaySettings(
            driver="protocol",
            host=host,
            port=port,
            username=self.settings.username,
            password=self.settings.password,
            use_tls=self.settings.use_tls,
            connect_timeout_seconds=self.settings.connect_timeout_seconds,
            read_timeout_seconds=self.settings.read_timeout_seconds,
        )

        with self._open_socket(runtime_settings) as connection:
            initial_state = self._read_packet(connection, expected_type="state")

            if command.kind == "connect":
                self._send_packet(connection, packet)
                self._read_response(connection, request_id=request_id)
                final_state = self._read_optional_state(connection) or initial_state
                event = state_event_from_packet(final_state)
                mode = "device" if packet.get("mode") == "interactive" else "simulated"
                status = ConnectionStatus.ONLINE if mode == "device" else ConnectionStatus.SIMULATED
                return ProtocolEventEnvelope(
                    kind="rabbit.connected",
                    connection_status=status,
                    payload={
                        "rabbit_slug": rabbit_slug,
                        "initial_state": initial_state,
                        "state": final_state,
                        "request": packet,
                    },
                )

            if command.kind == "disconnect":
                self._send_packet(connection, packet)
                self._read_response(connection, request_id=request_id)
                return ProtocolEventEnvelope(
                    kind="rabbit.disconnected",
                    connection_status=ConnectionStatus.OFFLINE,
                    payload={
                        "rabbit_slug": rabbit_slug,
                        "initial_state": initial_state,
                        "request": packet,
                    },
                )

            if command.kind == "sync":
                return state_event_from_packet(initial_state)

            if command.kind in {"info", "ears", "command"}:
                self._send_packet(connection, packet)
                response = self._read_response(connection, request_id=request_id)
                return ProtocolEventEnvelope(
                    kind=f"rabbit.{command.kind}.accepted",
                    connection_status=state_event_from_packet(initial_state).connection_status,
                    payload={
                        "rabbit_slug": rabbit_slug,
                        "initial_state": initial_state,
                        "request": packet,
                        "response": response.payload,
                        "wire": json.dumps(packet, separators=(",", ":")),
                    },
                )

            raise GatewayError(
                "Protocol client received an unsupported command kind "
                f"`{command.kind}` for {host}:{port}"
            )

    def _open_socket(self, settings: GatewaySettings) -> socket.socket:
        try:
            connection = socket.create_connection(
                (settings.host, settings.port),
                timeout=settings.connect_timeout_seconds,
            )
        except OSError as exc:
            raise GatewayError(
                f"Could not connect to nabd at {settings.host}:{settings.port}: {exc}"
            ) from exc
        connection.settimeout(settings.read_timeout_seconds)
        return connection

    def _send_packet(self, connection: socket.socket, packet: dict) -> None:
        connection.sendall((json.dumps(packet, separators=(",", ":")) + "\r\n").encode("utf-8"))

    def _read_packet(self, connection: socket.socket, expected_type: str | None = None) -> dict:
        line = self._read_line(connection)
        try:
            packet = json.loads(line)
        except json.JSONDecodeError as exc:
            raise GatewayError(f"Invalid JSON packet received from nabd: {line!r}") from exc
        packet_type = packet.get("type")
        if expected_type is not None and packet_type != expected_type:
            raise GatewayError(f"Expected `{expected_type}` packet from nabd, received `{packet_type}`")
        return packet

    def _read_optional_state(self, connection: socket.socket) -> dict | None:
        try:
            packet = self._read_packet(connection)
        except TimeoutError:
            return None
        if packet.get("type") == "state":
            return packet
        return None

    def _read_response(self, connection: socket.socket, request_id: str) -> ProtocolResponseEnvelope:
        packet = self._read_packet(connection, expected_type="response")
        if packet.get("request_id") != request_id:
            raise GatewayError(
                f"Unexpected response request_id from nabd: {packet.get('request_id')} != {request_id}"
            )
        status = packet.get("status")
        if status != "ok":
            message = packet.get("message") or status
            raise GatewayError(f"nabd returned non-ok response: {message}")
        return ProtocolResponseEnvelope(status=status, request_id=request_id, payload=packet)

    def _read_line(self, connection: socket.socket) -> str:
        buffer = bytearray()
        while True:
            try:
                chunk = connection.recv(1)
            except socket.timeout as exc:
                raise TimeoutError("Timed out while reading from nabd") from exc
            if not chunk:
                raise GatewayError("Connection to nabd closed unexpectedly")
            buffer.extend(chunk)
            if buffer.endswith(b"\n"):
                return buffer.decode("utf-8").strip()
