# Phase 0 Research: Cooperative Real-Time Glassworks

**Feature**: `001-glassworks` | **Date**: 2026-11-01

All Technical Context unknowns are resolved. Product-spec gaps are resolved as
design decisions and listed as prerequisites (P1) that MUST update both
`docs/spec.md` and `specs/001-glassworks/spec.md` before implementation.

## Specification Prerequisites (P1)

The current specification cannot be implemented as written without these
corrections. They are part of the first commit and are not to be silently
invented in code.

| ID | Gap | Resolution |
|----|-----|------------|
| P1.1 | No client events exist for opening or closing a season, yet rejection reasons reference `only master can open season` and `only master can close season` | Add `glassworks.start_requested` and `glassworks.close_requested` with empty payloads |
| P1.2 | A joining or reconnecting client receives no state until the next broadcast, because every event is a state-change fact | Add `state.synced` (server to requester, payload `{state}`) sent after successful role selection |
| P1.3 | Season table says initial `season` is 1 and each `glassworks.started` increments it, but T6 assumes an open season with `season=1`; the first start would therefore be season 2 | Start the internal counter at 0; the first `glassworks.started` sets it to 1; later starts increment by 1 |
| P1.4 | Rejection reasons do not cover invalid roles, unknown entities, malformed payloads, or opening an already-open season | Add `invalid role`, `unknown furnace`, `unknown bench`, `malformed payload`, `season already open` |
| P1.5 | Most events have no Test Cases scenario, violating Principle III/IV | Add one scenario per event using the Scenario Coverage Matrix below |

## R1. Role selection uses the Socket.IO connection auth payload

**Decision**: The login screen connects with
`socket.auth = {role: "master" | "player"}`. The server validates the role on
connect. It does not add a login event.

**Rationale**: Sessions must bind a role before any game event can be
authorized. The spec describes choosing a role on the login screen but defines
no login event, and adding one would expand the contract for no gameplay value.
Connection auth is the transport's native place for session identity.

**Alternatives considered**: A `session.join_requested` event (adds a
request/fact pair and a pre-join state where no role is known); a query string
(easily spoofed and awkward to change); browser storage plus a REST call
(violates the single-transport constraint).

## R2. Season lifecycle uses two explicit request events

**Decision**: Add `glassworks.start_requested` and
`glassworks.close_requested`. Both carry an empty payload, are Master-only, and
produce `glassworks.started` or `glassworks.closed` on success.

**Rationale**: The rejection list already implies these actions, and the
constitution requires client intents to end in `requested`. Emitting a server
fact directly from the UI would give clients apparent write authority.

**Alternatives considered**: UI-only buttons that mutate state locally (forbidden
by Principle I); overloading `glassmaking.requested` (mixes domains).

## R3. Season numbering starts at 0 internally; first start yields season 1

**Decision**: `GameState.season` is 0 before any season. Every
`glassworks.started` increments it, so the first open season is 1. This makes
T6's `season=1` reachable through gameplay.

**Rationale**: T6 and the purchase examples require an open season numbered 1.
The table's "initial 1" conflicts with its own "+1 on start" rule and with T6.
Starting at 0 preserves both the increment rule and the test intent. The
published state will show `season: 0` only while the lobby is closed; the UI
labels that as "no season yet".

**Alternatives considered**: Literal initial 1 with first start = 2 (contradicts
T6 and the cost examples); initial 1 with a special first start that does not
increment (breaks the stated rule and complicates reopen logic).

## R4. Time is a single epoch clock advanced by a tick loop

**Decision**: Define a `Clock` protocol with `now() -> float` returning epoch
seconds. `SystemClock` uses `time.time()`. `ManualClock` starts at a fixed epoch
and advances only when told. The domain exposes
`advance(now) -> list[Outbound]`; a transport task calls it every 50 ms. Due
events are processed in deadline order, with ties broken by type
(`sand`, `furnace`, `bench`) then entity id. A deadline is applied at its
scheduled time, not at the late tick time, so repeated ticks do not drift.

**Rationale**: Tick-based advancement makes every timer deterministic and
removes `asyncio` from the domain. Epoch timestamps make `cooling_ends_at`
meaningful to browsers. A single clock satisfies the constitution, and the
50 ms granularity is far below the 3 s minimum game duration.

**Alternatives considered**: Per-event `asyncio.sleep` tasks (hard to test, need
cancellation bookkeeping); a monotonic clock plus a separate wall clock (two
time sources); `call_later` injection (still couples the engine to the event
loop).

## R5. Atomicity comes from synchronous engine methods plus a transport lock

**Decision**: Every engine method validates and mutates synchronously, with no
`await`, and returns the outbound facts. The transport wraps
`validate + mutate + emit` for requests and ticks in one `asyncio.Lock`, then
broadcasts while holding it. No state snapshot is created across an `await`.

**Rationale**: Asyncio interleaves only at `await` points. Keeping mutation
synchronous makes T3's same-furnace race resolve to one success and one
`furnace busy`. Holding the lock through emission preserves fact order for
clients, preventing a later state from being displayed before an earlier one.

**Alternatives considered**: An outbound queue with a single writer (also valid,
but more moving parts); per-furnace locks (unnecessary with one synchronous
engine and one event loop).

## R6. Tests use the standard library plus the Socket.IO client

**Decision**: Use `unittest`, `unittest.IsolatedAsyncioTestCase`, `ManualClock`,
a seeded `random.Random`, and a recording broadcaster. Engine tests cover every
rule and rejection directly. One integration suite exercises every event over a
real local Socket.IO connection using `socketio.AsyncClient` against a
`uvicorn.Server` bound to a port-0 loopback socket via `Config.bind_socket`.
Tests never sleep; time is advanced explicitly.

**Rationale**: The constitution closes the runtime stack and requires
deterministic tests. `unittest` and the bundled Socket.IO client add no
dependency. Binding a pre-created socket removes port races. Testing the engine
directly gives fast, precise failure messages; the integration suite proves
event names, payloads, and broadcast targets.

**Alternatives considered**: `pytest`/`pytest-asyncio` (new dependency);
`asyncio.sleep` in tests (flaky and slow); testing only through sockets (poor
isolation and slow feedback).

## R7. Static files are served by a small stdlib ASGI wrapper

**Decision**: `static.py` inspects the ASGI scope path; paths beginning with
`/socket.io` go to `socketio.ASGIApp`, everything else maps to a file under
`web/`, with a safe resolved-path check, a small MIME map, 404, and `index.html`
fallback. `server.py` composes the two apps and starts the ticker on first
connect.

**Rationale**: The client is CDN-only and needs one origin for Socket.IO, so a
second process or permissive CORS is unnecessary. Starlette would add a
dependency excluded by Principle V.

**Alternatives considered**: `python -m http.server` alongside uvicorn (two
processes, CORS); adding Starlette (forbidden); serving from a CDN (deployment
complexity and another external service).

## R8. State snapshots are complete, serializable, and time-anchored

**Decision**: Every fact that changes state carries `state`, built fresh from
the model. The snapshot includes `server_time` (epoch seconds),
`season_open: bool`, `season`, `sand`, `glass`,
`glassblowers: {total, busy, free}`, `furnaces: [{id, piece_id}]`,
`benches: [{id, piece_id, cooling_ends_at}]`, and
`pieces: {id: {id, state, furnace_id, bench_id, ready_at, cooling_ends_at}}`.
`cooling_ends_at` is epoch seconds so the browser can render a countdown after
correcting with `server_time`.

**Rationale**: The constitution requires complete snapshots so clients never
replay history. Derived values are computed at serialization time and cannot
drift. Including `server_time` handles browser clock skew.

**Alternatives considered**: Deltas (rejected by the consistency constraint);
client-side derivation from partial data (allows divergence).

## R9. Rejection reasons are machine-readable and exhaustive

**Decision**: Add the P1.4 reasons and map validation as follows:

| Condition | Reason |
|-----------|--------|
| Non-dict payload, missing/wrong-type id, unknown request shape | `malformed payload` |
| Furnace id not 1..current count | `unknown furnace` |
| Bench id not 1..current count | `unknown bench` |
| Invalid or missing connection role | `invalid role` |
| Open request while already open | `season already open` |
| Any action while closed (except open) | `season not open` |
| Master tries a player action | `only players can interact` |
| Player tries to open/close | `only master can open season` / `only master can close season` |
| Second Master connection | `a master already exists` |
| All other existing spec conditions | Existing spec reasons unchanged |

**Rationale**: The constitution requires a documented reason for every rejected
path. Machine-readable strings keep client behavior deterministic.

**Alternatives considered**: A generic `invalid request` (loses actionable
client feedback); free-text errors (not testable).

## R10. Client is a thin Vue shell around a Phaser scene

**Decision**: Vue owns the login screen, HUD, purchases, and season controls;
Phaser owns the visual scene and maps furnace/bench ids to interactive objects.
`store.js` holds the latest server snapshot and exposes request helpers.
`scene.js` renders only from that snapshot. No game rule is computed for
authority; countdowns and affordability are display-only hints.

**Rationale**: Splitting UI chrome from the game canvas keeps Vue reactive and
Phaser's render loop focused, while the server remains authoritative.

**Alternatives considered**: Phaser-only UI (poor forms and accessibility);
Vue-only with DOM pieces (loses the canvas scene); a bundled SPA (violates the
no-build constraint).

## R11. Disconnect and reconnect semantics are stateless

**Decision**: Player disconnects remove only the session; their pieces remain.
Master disconnect while a season is open invokes the same close path with causa
`master_disconnected`, then releases the slot. Reconnecting clients perform the
login role selection again and receive `state.synced`. No session resume or
identity persistence exists.

**Rationale**: This is exactly the spec's T7 behavior and is the only policy
consistent with in-memory state and the one-Master rule.

**Alternatives considered**: Reassigning Master automatically (spec forbids);
persisting sessions (out of scope and requires storage).

## R12. Entity identifiers and selection are deterministic

**Decision**: Furnaces and benches start with id 1 and receive the next highest
id on purchase (cap 4). Pieces receive a monotonically increasing process-wide
id. A bench request chooses the lowest-id free bench. No random selection is
used outside crack chance.

**Rationale**: Deterministic ids and selection make tests and client rendering
stable, and they keep the server authoritative.

**Alternatives considered**: UUIDs (unreadable payloads, needless entropy);
random free-bench choice (nondeterministic tests).

## R13. Crack chance is a percentage and uses an injected RNG

**Decision**: At take time,
`elapsed = max(0, now - cooling_started_at)` and
`chance_percent = max(0, 1 - elapsed / 8) * 100`. The piece cracks when
`rng.random() * 100 < chance_percent`. The event payload `crack_chance` is that
percentage. The RNG is injected and seeded in tests.

**Rationale**: This matches the spec formula and T4 (0% after 8 s) and T5
(100% immediately). Percent matches the spec's `* 100%` wording.

**Alternatives considered**: Fraction 0..1 in the payload (ambiguous against the
spec); `random.random()` hard-coded (untestable).

## R14. Delivery is one commit per implementation stage

**Decision**: Follow the six stages in `plan.md`; each stage is one conventional
commit containing its tests and any spec updates it requires.

**Rationale**: Required by the constitution's staged-commit rule and keeps each
stage independently reviewable.

**Alternatives considered**: One large commit (unreviewable); per-file commits
(fragment a single stage).

## Scenario Coverage Matrix

Every event MUST gain at least one scenario in the Test Cases section of both
spec copies. Existing scenarios are extended rather than duplicated.

| Event | Scenario(s) to document |
|-------|-------------------------|
| `glassworks.start_requested` | S1 Master opens season (new) |
| `glassworks.started` | S1; setup of T4/T5/T6 |
| `glassworks.close_requested` | S2 Master closes season (new) |
| `glassworks.closed` | S2; T7 master disconnect |
| `glassmaking.requested` | T4; rejections T1, T3 |
| `glassmaking.started` | T4 |
| `glassmaking.heated` | T4 |
| `glassmaking.bench_requested` | T4; S4 bench busy (new) |
| `glassmaking.bench_started` | T4 |
| `glassmaking.completed` | T4 |
| `glass.take_requested` | T4, T5 |
| `glass.stored` | T4 |
| `glass.cracked` | T5 |
| `sand.stored` | T2 |
| `operation.rejected` | T1, T3, T6, T7, S3-S6 |
| `furnace.purchase_requested` | T6; S3 bench purchase (new) |
| `furnace.purchased` | T6 |
| `bench.purchase_requested` | S3 |
| `bench.purchased` | S3 |
| `state.synced` | S7 join mid-season (new) |

Additional proposed scenarios: S3 bench purchase, S4 bench-busy rejection,
S5 player tries to open a season, S6 unknown/malformed payload, S7 mid-season
join receives state.
