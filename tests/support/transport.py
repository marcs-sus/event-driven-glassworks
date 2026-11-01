"""In-process transport harness for integration tests.

The runtime dependency set intentionally excludes ``aiohttp``/``requests``,
so ``socketio.AsyncClient`` cannot be used here.  This harness starts uvicorn
on a pre-bound loopback socket and speaks the Engine.IO v4 long-polling
protocol with the standard library.  It exercises the real ASGI app, real
Socket.IO framing and real broadcasts without adding a dependency.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import socket
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import uvicorn


# ---------------------------------------------------------------------------
# Minimal HTTP/1.1 client
# ---------------------------------------------------------------------------


async def http_request(
    host: str,
    port: int,
    method: str,
    target: str,
    body: bytes = b"",
    headers: dict[str, str] | None = None,
    timeout: float = 5.0,
) -> tuple[int, dict[str, str], bytes]:
    """Perform one HTTP request and return ``(status, headers, body)``."""

    async def _do() -> tuple[int, dict[str, str], bytes]:
        reader, writer = await asyncio.open_connection(host, port)
        try:
            request_lines = [
                f"{method} {target} HTTP/1.1",
                f"Host: {host}:{port}",
                "Connection: close",
            ]
            for key, value in (headers or {}).items():
                request_lines.append(f"{key}: {value}")
            request_lines.append(f"Content-Length: {len(body)}")
            request_lines.append("")
            request_lines.append("")
            writer.write(
                "\r\n".join(request_lines).encode("latin-1") + body
            )
            await writer.drain()

            status_line = await reader.readline()
            if not status_line:
                raise ConnectionError("empty HTTP response")
            parts = status_line.decode("latin-1").strip().split(" ", 2)
            status = int(parts[1])

            response_headers: dict[str, str] = {}
            while True:
                line = await reader.readline()
                if line in (b"\r\n", b"\n", b""):
                    break
                key, _, value = line.decode("latin-1").partition(":")
                response_headers[key.strip().lower()] = value.strip()

            if response_headers.get(
                "transfer-encoding", ""
            ).lower() == "chunked":
                chunks: list[bytes] = []
                while True:
                    size_line = await reader.readline()
                    size = int(size_line.strip().split(b";")[0], 16)
                    if size == 0:
                        await reader.readline()
                        break
                    chunks.append(await reader.readexactly(size))
                    await reader.readexactly(2)
                response_body = b"".join(chunks)
            elif "content-length" in response_headers:
                response_body = await reader.readexactly(
                    int(response_headers["content-length"])
                )
            else:
                response_body = await reader.read()

            return status, response_headers, response_body
        finally:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()

    return await asyncio.wait_for(_do(), timeout=timeout)


# ---------------------------------------------------------------------------
# Engine.IO v4 / Socket.IO polling client
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Packet:
    kind: str
    name: str | None = None
    payload: Any = None


def decode_engineio_payload(body: bytes) -> list[Packet]:
    """Decode an Engine.IO v4 polling payload into Socket.IO packets."""

    packets: list[Packet] = []
    text = body.decode("utf-8")
    for raw in text.split("\x1e"):
        if not raw:
            continue
        engineio_type = raw[0]
        rest = raw[1:]

        if engineio_type == "0":
            packets.append(Packet("open", payload=json.loads(rest)))
        elif engineio_type == "2":
            packets.append(Packet("ping", payload=rest))
        elif engineio_type == "3":
            packets.append(Packet("pong", payload=rest))
        elif engineio_type == "4":
            if not rest:
                continue
            socketio_type = rest[0]
            data = rest[1:]
            if socketio_type == "0":
                packets.append(
                    Packet("connect", payload=json.loads(data or "{}"))
                )
            elif socketio_type == "1":
                packets.append(Packet("disconnect"))
            elif socketio_type == "2":
                event = json.loads(data)
                packets.append(
                    Packet(
                        "event",
                        name=event[0],
                        payload=event[1] if len(event) > 1 else None,
                    )
                )
            elif socketio_type == "3":
                packets.append(Packet("ack", payload=json.loads(data or "[]")))
            elif socketio_type == "4":
                packets.append(
                    Packet("error", payload=json.loads(data or "{}"))
                )
            else:
                packets.append(Packet("socketio", payload=rest))
        else:
            packets.append(Packet("engineio", payload=raw))

    return packets


class PollingClient:
    """A tiny Socket.IO client over Engine.IO v4 long-polling."""

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.sid: str | None = None
        self.socket_sid: str | None = None
        self.connected = False
        self.disconnected = False
        self.queue: list[Packet] = []
        self._counter = 0

    def _url(self, *, include_sid: bool) -> str:
        self._counter += 1
        target = (
            f"/socket.io/?EIO=4&transport=polling"
            f"&t={time.monotonic_ns()}-{self._counter}"
        )
        if include_sid:
            target += f"&sid={quote(self.sid or '')}"
        return target

    async def _post(self, data: str) -> None:
        status, _, _ = await http_request(
            self.host,
            self.port,
            "POST",
            self._url(include_sid=True),
            body=data.encode("utf-8"),
            headers={"Content-Type": "text/plain;charset=UTF-8"},
        )
        if status != 200:
            raise ConnectionError(f"POST failed with status {status}")

    async def _poll(self) -> None:
        status, _, body = await http_request(
            self.host,
            self.port,
            "GET",
            self._url(include_sid=True),
        )
        if status != 200:
            raise ConnectionError(f"GET failed with status {status}")

        for packet in decode_engineio_payload(body):
            if packet.kind == "ping":
                await self._post("3" + str(packet.payload or ""))
            elif packet.kind == "connect":
                self.connected = True
                if isinstance(packet.payload, dict):
                    self.socket_sid = packet.payload.get("sid")
            elif packet.kind == "disconnect":
                self.disconnected = True
                self.connected = False
            elif packet.kind in ("event", "error"):
                self.queue.append(packet)

    async def connect(self, role: str) -> "PollingClient":
        status, _, body = await http_request(
            self.host,
            self.port,
            "GET",
            self._url(include_sid=False),
        )
        if status != 200:
            raise ConnectionError(f"handshake failed with status {status}")

        opened = [
            packet
            for packet in decode_engineio_payload(body)
            if packet.kind == "open"
        ]
        if not opened:
            raise ConnectionError("server did not send an Engine.IO open packet")

        self.sid = opened[0].payload["sid"]
        auth = json.dumps({"role": role}, separators=(",", ":"))
        await self._post("40" + auth)
        return self

    async def wait_for(self, name: str, timeout: float = 5.0) -> Any:
        """Return the payload of the next event called ``name``."""

        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while True:
            for index, packet in enumerate(self.queue):
                if packet.kind == "event" and packet.name == name:
                    self.queue.pop(index)
                    return packet.payload

            remaining = deadline - loop.time()
            if remaining <= 0:
                raise TimeoutError(f"timed out waiting for {name}")

            await asyncio.wait_for(self._poll(), timeout=remaining)

    async def close(self) -> None:
        if self.sid and not self.disconnected:
            with contextlib.suppress(Exception):
                await self._post("41")
        self.sid = None


# ---------------------------------------------------------------------------
# uvicorn harness
# ---------------------------------------------------------------------------


class _TestServer(uvicorn.Server):
    def __init__(self, config: uvicorn.Config, started: asyncio.Event) -> None:
        super().__init__(config)
        self._started_event = started

    async def startup(self, sockets: list[socket.socket] | None = None) -> None:
        await super().startup(sockets=sockets)
        self._started_event.set()


class TransportHarness:
    """Run an ASGI app on a port-0 loopback socket."""

    def __init__(self, app: Any) -> None:
        self.app = app
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind(("127.0.0.1", 0))
        self._socket.listen(128)
        self.port = self._socket.getsockname()[1]
        self._started = asyncio.Event()
        self._server = _TestServer(
            uvicorn.Config(
                app,
                log_level="warning",
                lifespan="on",
                access_log=False,
            ),
            self._started,
        )
        self._task: asyncio.Task[Any] | None = None
        self.clients: list[PollingClient] = []

    async def start(self) -> "TransportHarness":
        self._task = asyncio.create_task(
            self._server.serve(sockets=[self._socket])
        )
        await asyncio.wait_for(self._started.wait(), timeout=5.0)
        return self

    async def connect(self, role: str) -> PollingClient:
        client = PollingClient("127.0.0.1", self.port)
        await client.connect(role)
        self.clients.append(client)
        return client

    async def stop(self) -> None:
        for client in self.clients:
            await client.close()
        self._server.should_exit = True
        if self._task is not None:
            await asyncio.wait_for(self._task, timeout=5.0)
            self._task = None
        with contextlib.suppress(OSError):
            self._socket.close()
