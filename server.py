"""Cooperative Real-Time Glassworks server.

A single-process ASGI application organised into clearly commented sections:

1. clock      -- injectable time source
2. events     -- the event-name registry, cause values and rejection reasons
3. rules      -- every game constant and pure formula
4. models     -- dataclasses, enums and the state snapshot serializer
5. engine     -- synchronous, transport-free state machine
6. transport  -- Socket.IO handlers, auth, broadcasts and the tick loop
7. static     -- stdlib ASGI static-file wrapper (client/ and /assets)
8. entry      -- ASGI app factory; run with ``uvicorn server:app``

Phase 2 intentionally implements only the connection flow:

* role selection from the Socket.IO connection auth payload
* the single-Master slot
* one ``state.synced`` snapshot per accepted connection
* ``operation.rejected`` for connection validation failures

No season, production, sand, purchase or disconnect-close behaviour is
implemented here; those arrive in later phases.
"""

from __future__ import annotations

import asyncio
import contextlib
import posixpath
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import unquote, urlsplit

import socketio

# ---------------------------------------------------------------------------
# 1. clock
# ---------------------------------------------------------------------------

#: A stable epoch used by ManualClock so tests never depend on wall time.
DEFAULT_EPOCH = 1_767_225_600.0


class Clock(Protocol):
    """A source of epoch seconds."""

    def now(self) -> float:  # pragma: no cover - protocol declaration
        ...


class SystemClock:
    """Wall-clock implementation used by the running server."""

    def now(self) -> float:
        return time.time()


class ManualClock:
    """Deterministic clock for tests and local experiments."""

    def __init__(self, start: float = DEFAULT_EPOCH) -> None:
        self._now = float(start)

    def now(self) -> float:
        return self._now

    def advance(self, seconds: float) -> float:
        self._now += float(seconds)
        return self._now

    def set(self, value: float) -> None:
        self._now = float(value)


# ---------------------------------------------------------------------------
# 2. events
# ---------------------------------------------------------------------------


class Event(str, Enum):
    """Every event name in the contract.

    Phase 2 registers only ``state.synced`` and ``operation.rejected``; the
    remaining names are defined now so later phases cannot drift from the
    contract.
    """

    STATE_SYNCED = "state.synced"
    OPERATION_REJECTED = "operation.rejected"

    GLASSWORKS_START_REQUESTED = "glassworks.start_requested"
    GLASSWORKS_STARTED = "glassworks.started"
    GLASSWORKS_CLOSE_REQUESTED = "glassworks.close_requested"
    GLASSWORKS_CLOSED = "glassworks.closed"

    GLASSMAKING_REQUESTED = "glassmaking.requested"
    GLASSMAKING_STARTED = "glassmaking.started"
    GLASSMAKING_HEATED = "glassmaking.heated"
    GLASSMAKING_BENCH_REQUESTED = "glassmaking.bench_requested"
    GLASSMAKING_BENCH_STARTED = "glassmaking.bench_started"
    GLASSMAKING_COMPLETED = "glassmaking.completed"

    GLASS_TAKE_REQUESTED = "glass.take_requested"
    GLASS_STORED = "glass.stored"
    GLASS_CRACKED = "glass.cracked"

    SAND_STORED = "sand.stored"

    FURNACE_PURCHASE_REQUESTED = "furnace.purchase_requested"
    FURNACE_PURCHASED = "furnace.purchased"
    BENCH_PURCHASE_REQUESTED = "bench.purchase_requested"
    BENCH_PURCHASED = "bench.purchased"


REQUEST_EVENTS: tuple[str, ...] = (
    Event.GLASSWORKS_START_REQUESTED.value,
    Event.GLASSWORKS_CLOSE_REQUESTED.value,
    Event.GLASSMAKING_REQUESTED.value,
    Event.GLASSMAKING_BENCH_REQUESTED.value,
    Event.GLASS_TAKE_REQUESTED.value,
    Event.FURNACE_PURCHASE_REQUESTED.value,
    Event.BENCH_PURCHASE_REQUESTED.value,
)

FACT_EVENTS: tuple[str, ...] = (
    Event.GLASSWORKS_STARTED.value,
    Event.GLASSWORKS_CLOSED.value,
    Event.GLASSMAKING_STARTED.value,
    Event.GLASSMAKING_HEATED.value,
    Event.GLASSMAKING_BENCH_STARTED.value,
    Event.GLASSMAKING_COMPLETED.value,
    Event.GLASS_STORED.value,
    Event.GLASS_CRACKED.value,
    Event.SAND_STORED.value,
    Event.FURNACE_PURCHASED.value,
    Event.BENCH_PURCHASED.value,
)


class Cause(str, Enum):
    """Why a fact happened."""

    MASTER = "master"
    PLAYER = "player"
    TIMER = "timer"
    SAND_TICK = "sand_tick"
    MASTER_DISCONNECTED = "master_disconnected"
    CONNECTION = "connection"


class Rejection(str, Enum):
    """Every documented ``operation.rejected`` reason."""

    SEASON_NOT_OPEN = "season not open"
    SEASON_ALREADY_OPEN = "season already open"
    NOT_ENOUGH_SAND = "not enough sand"
    NOT_ENOUGH_GLASS = "not enough glass"
    NO_FREE_WORKER = "no free worker"
    FURNACE_BUSY = "furnace busy"
    BENCH_BUSY = "bench busy"
    PIECE_NOT_READY = "piece not ready"
    MAX_FURNACES_REACHED = "max furnaces reached"
    MAX_BENCHES_REACHED = "max benches reached"
    ONLY_MASTER_CAN_OPEN_SEASON = "only master can open season"
    ONLY_MASTER_CAN_CLOSE_SEASON = "only master can close season"
    ONLY_PLAYERS_CAN_INTERACT = "only players can interact"
    MASTER_ALREADY_EXISTS = "a master already exists"
    INVALID_ROLE = "invalid role"
    UNKNOWN_FURNACE = "unknown furnace"
    UNKNOWN_BENCH = "unknown bench"
    MALFORMED_PAYLOAD = "malformed payload"
    NO_PIECE_TO_TAKE = "no piece to take"


# ---------------------------------------------------------------------------
# 3. rules
# ---------------------------------------------------------------------------

INITIAL_SAND = 12
SAND_CAP = 30
SAND_PER_PIECE = 3
SAND_REFILL = 6
SAND_REFILL_INTERVAL_SECONDS = 10.0
WORKERS_TOTAL = 8
INITIAL_FURNACES = 1
INITIAL_BENCHES = 1
MAX_FURNACES = 4
MAX_BENCHES = 4
HEATING_SECONDS = 5.0
BENCH_SECONDS = 3.0
COOLING_SECONDS = 8.0


def sand_refill(sand: int) -> int:
    """Sand gained by one tick: ``min(6, 30 - sand)``."""

    return min(SAND_REFILL, SAND_CAP - sand)


def purchase_cost(count: int, season: int) -> int:
    """Cost of the next furnace or bench: ``count * season * 2 + 1``."""

    return count * season * 2 + 1


def crack_chance(elapsed_cooling: float) -> float:
    """Percentage chance that a taken piece cracks."""

    return max(0.0, 1.0 - elapsed_cooling / COOLING_SECONDS) * 100.0


# ---------------------------------------------------------------------------
# 4. models
# ---------------------------------------------------------------------------


class Role(str, Enum):
    MASTER = "master"
    PLAYER = "player"


class PieceState(str, Enum):
    FURNACE_HEATING = "furnace_heating"
    FURNACE_READY = "furnace_ready"
    BENCH_WORKING = "bench_working"
    BENCH_COOLING = "bench_cooling"


BUSY_PIECE_STATES = frozenset(
    {
        PieceState.FURNACE_HEATING,
        PieceState.FURNACE_READY,
        PieceState.BENCH_WORKING,
    }
)


@dataclass
class Furnace:
    id: int
    piece_id: int | None = None

    def __post_init__(self) -> None:
        if not 1 <= self.id <= MAX_FURNACES:
            raise ValueError("furnace id must be between 1 and 4")
        if self.piece_id is not None and self.piece_id < 1:
            raise ValueError("piece id must be positive")


@dataclass
class Bench:
    id: int
    piece_id: int | None = None
    cooling_ends_at: float | None = None

    def __post_init__(self) -> None:
        if not 1 <= self.id <= MAX_BENCHES:
            raise ValueError("bench id must be between 1 and 4")
        if self.piece_id is not None and self.piece_id < 1:
            raise ValueError("piece id must be positive")


@dataclass
class Piece:
    id: int
    state: PieceState
    furnace_id: int | None = None
    bench_id: int | None = None
    ready_at: float | None = None
    cooling_started_at: float | None = None
    cooling_ends_at: float | None = None

    def __post_init__(self) -> None:
        if self.id < 1:
            raise ValueError("piece id must be positive")
        if not isinstance(self.state, PieceState):
            self.state = PieceState(self.state)
        if self.state in (PieceState.FURNACE_HEATING, PieceState.FURNACE_READY):
            if self.furnace_id is None or self.bench_id is not None:
                raise ValueError("furnace pieces must reference only a furnace")
        else:
            if self.bench_id is None or self.furnace_id is not None:
                raise ValueError("bench pieces must reference only a bench")


@dataclass
class GameState:
    """The single shared room."""

    season: int = 0
    season_open: bool = False
    sand: int = INITIAL_SAND
    glass: int = 0
    glassblowers_total: int = WORKERS_TOTAL
    glassblowers_busy: int = 0
    furnaces: dict[int, Furnace] = field(
        default_factory=lambda: {1: Furnace(1)}
    )
    benches: dict[int, Bench] = field(default_factory=lambda: {1: Bench(1)})
    pieces: dict[int, Piece] = field(default_factory=dict)
    next_piece_id: int = 1
    next_furnace_id: int = INITIAL_FURNACES + 1
    next_bench_id: int = INITIAL_BENCHES + 1
    next_sand_tick_at: float | None = None

    def __post_init__(self) -> None:
        self.validate()

    def busy_count(self) -> int:
        return sum(
            1
            for piece in self.pieces.values()
            if piece.state in BUSY_PIECE_STATES
        )

    def validate(self) -> None:
        if self.season < 0:
            raise ValueError("season must be non-negative")
        if not 0 <= self.sand <= SAND_CAP:
            raise ValueError("sand must be between 0 and 30")
        if self.glass < 0:
            raise ValueError("glass must be non-negative")
        if self.glassblowers_total != WORKERS_TOTAL:
            raise ValueError("glassblowers_total is fixed at 8")
        if not 0 <= self.glassblowers_busy <= WORKERS_TOTAL:
            raise ValueError("glassblowers_busy must be between 0 and 8")
        if not 1 <= len(self.furnaces) <= MAX_FURNACES:
            raise ValueError("there must be between 1 and 4 furnaces")
        if not 1 <= len(self.benches) <= MAX_BENCHES:
            raise ValueError("there must be between 1 and 4 benches")
        if self.glassblowers_busy != self.busy_count():
            raise ValueError("glassblowers_busy must match active pieces")
        if not self.season_open and (self.pieces or self.glassblowers_busy):
            raise ValueError("a closed season cannot have pieces or busy workers")

        referenced: set[int] = set()
        for furnace in self.furnaces.values():
            if furnace.piece_id is None:
                continue
            if furnace.piece_id in referenced:
                raise ValueError("a piece cannot be held by two containers")
            referenced.add(furnace.piece_id)
            piece = self.pieces.get(furnace.piece_id)
            if piece is None:
                raise ValueError("furnace references an unknown piece")
            if piece.furnace_id != furnace.id:
                raise ValueError("piece and furnace disagree about ownership")
            if piece.state not in (
                PieceState.FURNACE_HEATING,
                PieceState.FURNACE_READY,
            ):
                raise ValueError("furnace holds a piece in the wrong state")

        for bench in self.benches.values():
            if bench.piece_id is None:
                continue
            if bench.piece_id in referenced:
                raise ValueError("a piece cannot be held by two containers")
            referenced.add(bench.piece_id)
            piece = self.pieces.get(bench.piece_id)
            if piece is None:
                raise ValueError("bench references an unknown piece")
            if piece.bench_id != bench.id:
                raise ValueError("piece and bench disagree about ownership")
            if piece.state not in (
                PieceState.BENCH_WORKING,
                PieceState.BENCH_COOLING,
            ):
                raise ValueError("bench holds a piece in the wrong state")
            if bench.cooling_ends_at != piece.cooling_ends_at:
                raise ValueError("bench and piece disagree about cooling")

        if set(self.pieces) != referenced:
            raise ValueError("every piece must be held by one container")

    def snapshot(self, now: float) -> dict[str, Any]:
        """Serialize to the shape in ``contracts/state.schema.json``."""

        busy = self.busy_count()
        return {
            "server_time": float(now),
            "season": self.season,
            "season_open": self.season_open,
            "sand": self.sand,
            "glass": self.glass,
            "glassblowers": {
                "total": self.glassblowers_total,
                "busy": busy,
                "free": self.glassblowers_total - busy,
            },
            "furnaces": [
                {"id": furnace.id, "piece_id": furnace.piece_id}
                for furnace in sorted(
                    self.furnaces.values(), key=lambda item: item.id
                )
            ],
            "benches": [
                {
                    "id": bench.id,
                    "piece_id": bench.piece_id,
                    "cooling_ends_at": bench.cooling_ends_at,
                }
                for bench in sorted(
                    self.benches.values(), key=lambda item: item.id
                )
            ],
            "pieces": {
                str(piece_id): {
                    "id": piece.id,
                    "state": piece.state.value,
                    "furnace_id": piece.furnace_id,
                    "bench_id": piece.bench_id,
                    "ready_at": piece.ready_at,
                    "cooling_started_at": piece.cooling_started_at,
                    "cooling_ends_at": piece.cooling_ends_at,
                }
                for piece_id, piece in sorted(self.pieces.items())
            },
        }


# ---------------------------------------------------------------------------
# 5. engine
# ---------------------------------------------------------------------------


class MasterSlotTaken(Exception):
    """Raised when a second Master tries to join."""


@dataclass
class Session:
    sid: str
    role: Role
    name: str | None = None


@dataclass(frozen=True)
class Fact:
    """A server fact ready for broadcast."""

    event: str
    payload: dict[str, Any]


class Engine:
    """Synchronous, transport-free state machine skeleton."""

    def __init__(
        self,
        clock: Clock,
        rng: random.Random | None = None,
    ) -> None:
        self.clock = clock
        self.rng = rng or random.Random()
        self.state = GameState()
        self.sessions: dict[str, Session] = {}
        self.master_sid: str | None = None

    # -- sessions ---------------------------------------------------------

    def join(self, sid: str, role: Role, name: str | None = None) -> Session:
        existing = self.sessions.get(sid)
        if existing is not None:
            return existing
        if role is Role.MASTER:
            if self.master_sid is not None:
                raise MasterSlotTaken()
            self.master_sid = sid
        session = Session(sid=sid, role=role, name=name)
        self.sessions[sid] = session
        return session

    def leave(self, sid: str) -> Session | None:
        session = self.sessions.pop(sid, None)
        if self.master_sid == sid:
            self.master_sid = None
        return session

    # -- snapshots and helpers -------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        return self.state.snapshot(self.clock.now())

    def busy_count(self) -> int:
        return self.state.busy_count()

    def allocate_piece_id(self) -> int:
        piece_id = self.state.next_piece_id
        self.state.next_piece_id += 1
        return piece_id

    def allocate_furnace_id(self) -> int:
        furnace_id = self.state.next_furnace_id
        self.state.next_furnace_id += 1
        return furnace_id

    def allocate_bench_id(self) -> int:
        bench_id = self.state.next_bench_id
        self.state.next_bench_id += 1
        return bench_id

    # -- advancement ------------------------------------------------------

    def advance(self, now: float) -> list[Fact]:
        """Process due deadlines and return facts to broadcast.

        Phase 2 has no scheduled game behaviour, so this is intentionally a
        no-op. Later phases add sand, furnace and bench deadlines here.
        """

        return []


# ---------------------------------------------------------------------------
# 6. transport
# ---------------------------------------------------------------------------

TICK_INTERVAL_SECONDS = 0.05


class Glassworks:
    """Socket.IO transport around a synchronous Engine."""

    def __init__(
        self,
        clock: Clock | None = None,
        rng: random.Random | None = None,
    ) -> None:
        self.clock = clock or SystemClock()
        self.engine = Engine(self.clock, rng)
        self.lock = asyncio.Lock()
        self.sio = socketio.AsyncServer(
            async_mode="asgi",
            cors_allowed_origins="*",
            logger=False,
            engineio_logger=False,
        )
        self.socket_app = socketio.ASGIApp(self.sio)
        self._tasks: set[asyncio.Task[Any]] = set()
        self._ticker_task: asyncio.Task[Any] | None = None

        self.sio.on("connect", self._handle_connect)
        self.sio.on("disconnect", self._handle_disconnect)

    # -- task bookkeeping -------------------------------------------------

    def _spawn(self, coro: Any) -> asyncio.Task[Any]:
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    @property
    def ticker_task(self) -> asyncio.Task[Any] | None:
        return self._ticker_task

    @property
    def pending_tasks(self) -> frozenset[asyncio.Task[Any]]:
        return frozenset(self._tasks)

    def start_ticker(self) -> None:
        if self._ticker_task is None or self._ticker_task.done():
            self._ticker_task = asyncio.create_task(
                self._tick_loop(), name="glassworks-tick"
            )

    async def stop(self) -> None:
        """Cancel the ticker and every deferred connection task."""

        ticker = self._ticker_task
        self._ticker_task = None
        if ticker is not None:
            ticker.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await ticker

        pending = list(self._tasks)
        for task in pending:
            task.cancel()
        for task in pending:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._tasks.clear()

    # -- handlers ---------------------------------------------------------

    async def _handle_connect(
        self,
        sid: str,
        environ: dict[str, Any],
        auth: Any,
    ) -> None:
        role_value = auth.get("role") if isinstance(auth, dict) else None

        if role_value not in (Role.MASTER.value, Role.PLAYER.value):
            self._spawn(self._reject_later(sid, Rejection.INVALID_ROLE.value))
            return

        async with self.lock:
            if (
                role_value == Role.MASTER.value
                and self.engine.master_sid is not None
            ):
                self._spawn(
                    self._reject_later(
                        sid, Rejection.MASTER_ALREADY_EXISTS.value
                    )
                )
                return
            self.engine.join(sid, Role(role_value))

        # Socket.IO writes packets emitted during the connect handler before
        # its acknowledgement. Deferring one loop turn lets the client finish
        # connecting before it receives state.synced.
        self._spawn(self._sync_later(sid))

    async def _handle_disconnect(
        self, sid: str, reason: str | None = None
    ) -> None:
        async with self.lock:
            self.engine.leave(sid)
            # Phase 6 adds: if this was the Master and the season is open,
            # close it with cause master_disconnected before releasing.

    async def _sync_later(self, sid: str) -> None:
        await asyncio.sleep(0)
        async with self.lock:
            payload = {
                "state": self.engine.snapshot(),
                "causa": Cause.CONNECTION.value,
            }
            await self.sio.emit(
                Event.STATE_SYNCED.value, payload, to=sid
            )

    async def _reject_later(self, sid: str, reason: str) -> None:
        await asyncio.sleep(0)
        with contextlib.suppress(Exception):
            await self.sio.emit(
                Event.OPERATION_REJECTED.value,
                {
                    "causa": Cause.CONNECTION.value,
                    "reason": reason,
                },
                to=sid,
            )
            await self.sio.disconnect(sid)

    # -- broadcasting and ticking ----------------------------------------

    async def broadcast(self, event: str, payload: dict[str, Any]) -> None:
        await self.sio.emit(event, payload)

    async def _tick_loop(self) -> None:
        while True:
            await asyncio.sleep(TICK_INTERVAL_SECONDS)
            async with self.lock:
                facts = self.engine.advance(self.clock.now())
                for fact in facts:
                    await self.broadcast(fact.event, fact.payload)


# ---------------------------------------------------------------------------
# 7. static
# ---------------------------------------------------------------------------

CLIENT_ROOT = (Path(__file__).resolve().parent / "client").resolve()
CLIENT_FILE = CLIENT_ROOT / "index.html"

MIME_TYPES: dict[str, str] = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".map": "application/json; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
    ".ico": "image/x-icon",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".txt": "text/plain; charset=utf-8",
}

STATIC_PREFIXES: tuple[tuple[str, Path], ...] = (
    ("/assets/", CLIENT_ROOT / "assets"),
    ("/css/", CLIENT_ROOT / "css"),
    ("/js/", CLIENT_ROOT / "js"),
)


def _safe_client_file(url_path: str) -> Path | None:
    """Resolve a URL path to a file inside ``client/``, or ``None``."""

    raw_path = unquote(urlsplit(url_path).path)
    path = posixpath.normpath(raw_path)

    if path in ("/", "/index.html"):
        return CLIENT_FILE

    for prefix, root in STATIC_PREFIXES:
        if not path.startswith(prefix):
            continue
        relative = path[len(prefix) :]
        if not relative:
            return None
        candidate = (root / relative).resolve()
        try:
            candidate.relative_to(root.resolve())
        except ValueError:
            return None
        return candidate if candidate.is_file() else None

    # Extensionless paths fall back to the single-page client.
    if "." not in posixpath.basename(path):
        return CLIENT_FILE if CLIENT_FILE.is_file() else None
    return None


def _content_type(path: Path) -> str:
    return MIME_TYPES.get(
        path.suffix.lower(), "application/octet-stream"
    )


class GlassworksApp:
    """ASGI composition: lifespan, Socket.IO delegation and static files."""

    def __init__(self, game: Glassworks) -> None:
        self.game = game
        self.socket_app = game.socket_app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        scope_type = scope.get("type")

        if scope_type == "lifespan":
            await self._lifespan(receive, send)
            return

        path = scope.get("path", "")
        if scope_type in ("http", "websocket") and path.startswith(
            "/socket.io"
        ):
            await self.socket_app(scope, receive, send)
            return

        if scope_type == "http":
            await self._serve_http(scope, receive, send)
            return

        if scope_type == "websocket":
            await send({"type": "websocket.close", "code": 1000})
            return

    async def _lifespan(self, receive: Any, send: Any) -> None:
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                self.game.start_ticker()
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                await self.game.stop()
                await send({"type": "lifespan.shutdown.complete"})
                return

    async def _serve_http(
        self, scope: dict[str, Any], receive: Any, send: Any
    ) -> None:
        method = scope.get("method", "GET").upper()
        if method not in ("GET", "HEAD"):
            await self._respond(
                send,
                405,
                b"Method not allowed",
                "text/plain; charset=utf-8",
                head=False,
            )
            return

        path = scope.get("path", "/")
        file_path = _safe_client_file(path)
        if file_path is None:
            await self._respond(
                send,
                404,
                b"Not found",
                "text/plain; charset=utf-8",
                head=method == "HEAD",
            )
            return

        try:
            body = file_path.read_bytes()
        except OSError:
            await self._respond(
                send,
                404,
                b"Not found",
                "text/plain; charset=utf-8",
                head=method == "HEAD",
            )
            return

        await self._respond(
            send,
            200,
            body,
            _content_type(file_path),
            head=method == "HEAD",
            cache="no-store" if file_path == CLIENT_FILE else "no-cache",
        )

    async def _respond(
        self,
        send: Any,
        status: int,
        body: bytes,
        content_type: str,
        *,
        head: bool,
        cache: str = "no-store",
    ) -> None:
        headers = [
            (b"content-type", content_type.encode("ascii")),
            (b"content-length", str(len(body)).encode("ascii")),
            (b"cache-control", cache.encode("ascii")),
            (b"access-control-allow-origin", b"*"),
        ]
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": headers,
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": b"" if head else body,
            }
        )


# ---------------------------------------------------------------------------
# 8. entry
# ---------------------------------------------------------------------------


def create_app(
    clock: Clock | None = None,
    rng: random.Random | None = None,
) -> GlassworksApp:
    """Build a fresh application (useful for tests and embedded servers)."""

    return GlassworksApp(Glassworks(clock=clock, rng=rng))


#: The ASGI entry point used by ``uvicorn server:app``.
app = create_app()


if __name__ == "__main__":  # pragma: no cover - convenience entry point
    import uvicorn

    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
