# Event Contract: Cooperative Real-Time Glassworks

**Feature**: `001-glassworks` | **Date**: 2026-11-01

This contract is normative for the server, the browser client, and the tests.
It extends the event table in `docs/spec.md` with the prerequisite changes in
`research.md` (P1). Names follow the constitution: server facts use
`object.action_past`; client requests end in `requested`.

## Transport

- One Socket.IO namespace (`/`) over WebSocket, with polling fallback.
- One shared room; every connected, authenticated session receives every server
  fact except `state.synced` and `operation.rejected`, which are unicast.
- JSON payloads only. Unknown top-level fields are ignored.
- A client MUST NOT emit any event not listed as a client request.

## Connection Handshake

Role selection happens in the Socket.IO connection auth payload, not in a game
event (R1).

```json
{ "role": "master" }
```

or

```json
{ "role": "player" }
```

| Condition | Result |
|-----------|--------|
| Valid role, master slot free (or player) | Connection accepted; server emits `state.synced` to the new session |
| Role missing or not `master`/`player` | Server emits `operation.rejected` (`invalid role`, causa `connection`) to that session, then disconnects it |
| `role = "master"` while a Master is connected | Server emits `operation.rejected` (`a master already exists`, causa `connection`) to that session, then disconnects it |

A Master disconnect while a season is open closes the season with causa
`master_disconnected` before the slot is released (T7).

## Conventions

- `state` is the complete snapshot defined in `contracts/state.schema.json`.
  Every fact that changes state includes it.
- `causa` identifies what triggered a fact: `master`, `player`, `timer`,
  `sand_tick`, `master_disconnected`, or `connection`.
- Identifiers are integers. `crack_chance` is a percentage in `[0, 100]`.
  `cooling_ends_at`, `ready_at`, and `server_time` are epoch seconds.
- Every rejection is unicast as `operation.rejected` and never mutates state.

## Client Requests (client → server)

| Event | Payload | Eligible role | Success fact |
|-------|---------|---------------|--------------|
| `glassworks.start_requested` | `{}` | Master | `glassworks.started` |
| `glassworks.close_requested` | `{}` | Master | `glassworks.closed` |
| `glassmaking.requested` | `{ "furnace_id": int }` | Player | `glassmaking.started` |
| `glassmaking.bench_requested` | `{ "furnace_id": int }` | Player | `glassmaking.bench_started` |
| `glass.take_requested` | `{ "bench_id": int }` | Player | `glass.stored` or `glass.cracked` |
| `furnace.purchase_requested` | `{}` | Player | `furnace.purchased` |
| `bench.purchase_requested` | `{}` | Player | `bench.purchased` |

`glassworks.start_requested` and `glassworks.close_requested` are prerequisites
P1.1 and MUST be added to both spec copies before implementation.

## Server Facts (server → everyone)

### `glassworks.started`

```json
{ "state": { }, "causa": "master" }
```

Effects: `season += 1`; `season_open = true`; `sand = 12`; `glass = 0`; all
pieces removed; furnaces and benches persist but are emptied; workers freed;
sand tick scheduled at `server_time + 10`.

### `glassworks.closed`

```json
{ "state": { }, "causa": "master" }
```

`causa` is `master` for an explicit close or `master_disconnected` for T7.
Effects: `season_open = false`; all pieces removed; furnaces and benches emptied;
workers freed; sand and glass unchanged; sand tick cancelled.

### `glassmaking.started`

```json
{ "state": { }, "causa": "player", "furnace_id": 1 }
```

Effects: `sand -= 3`; one worker busy; piece created in `furnace_heating` with
`ready_at = server_time + 5`.

### `glassmaking.heated`

```json
{ "state": { }, "causa": "timer", "furnace_id": 1 }
```

Effects: the piece becomes `furnace_ready`; the worker remains busy.

### `glassmaking.bench_started`

```json
{ "state": { }, "causa": "player", "furnace_id": 1, "bench_id": 1 }
```

Effects: the ready piece leaves the furnace; the lowest-id free bench is
occupied; the piece becomes `bench_working` with `ready_at = server_time + 3`.

### `glassmaking.completed`

```json
{ "state": { }, "causa": "timer", "bench_id": 1, "cooling_ends_at": 1767225608.0 }
```

Effects: the piece becomes `bench_cooling`; the worker is freed;
`cooling_ends_at = bench_ready_at + 8`. The piece is takeable immediately, with
a crack chance that falls to 0 at `cooling_ends_at`.

### `glass.stored`

```json
{ "state": { }, "causa": "player", "bench_id": 1 }
```

Effects: `glass += 1`; the bench is freed; the piece is removed.

### `glass.cracked`

```json
{ "state": { }, "causa": "player", "bench_id": 1, "crack_chance": 100.0 }
```

Effects: glass is unchanged; the bench is freed; the piece is removed.

### `sand.stored`

```json
{ "state": { }, "causa": "sand_tick", "gained": 6 }
```

Effects: `gained = min(6, 30 - sand)`; `sand += gained`; next tick scheduled
10 s later. Emitted every 10 s while open, including `gained: 0` at the cap (T2).

### `furnace.purchased`

```json
{ "state": { }, "causa": "player", "furnace_id": 2, "cost": 3 }
```

Effects: `glass -= cost`; a furnace with `furnace_id` is added.
`cost = current_furnace_count * season * 2 + 1` before adding.

### `bench.purchased`

```json
{ "state": { }, "causa": "player", "bench_id": 2, "cost": 3 }
```

Effects: `glass -= cost`; a bench with `bench_id` is added.
`cost = current_bench_count * season * 2 + 1` before adding.

## Server Unicast

### `state.synced`

Sent to a newly authenticated session (including reconnects) so no client waits
for the next fact (P1.2).

```json
{ "state": { } }
```

### `operation.rejected`

Sent only to the requester. Never mutates state.

```json
{ "causa": "player", "reason": "not enough sand" }
```

`causa` is `connection` for handshake rejections, otherwise the request's cause.

## Rejection Reasons

| Reason | Trigger |
|--------|---------|
| `season not open` | Any gameplay action while the season is closed |
| `season already open` | `glassworks.start_requested` while open |
| `not enough sand` | Piece request with `sand < 3` |
| `not enough glass` | Purchase with `glass < cost` |
| `no free worker` | Piece request with all 8 workers busy |
| `furnace busy` | Piece request on an occupied furnace |
| `bench busy` | Bench request with no free bench |
| `piece not ready` | Bench request on a non-ready furnace, or take on a non-cooling piece |
| `max furnaces reached` | Furnace purchase with 4 furnaces |
| `max benches reached` | Bench purchase with 4 benches |
| `only master can open season` | Non-Master sends `glassworks.start_requested` |
| `only master can close season` | Non-Master sends `glassworks.close_requested` |
| `a master already exists` | Second Master connects |
| `only players can interact` | Master sends a production or purchase request |
| `no piece to take` | Take request on an empty bench |
| `invalid role` | Connection auth role missing or unknown |
| `unknown furnace` | Furnace id outside `1..furnace_count` |
| `unknown bench` | Bench id outside `1..bench_count` |
| `malformed payload` | Payload is not a mapping or a required id is missing/not an integer |

The evaluation order when several conditions fail is defined in
`data-model.md`; the first failing check determines the reason.

## Flows

### Open and produce (T4)

```text
Master -> glassworks.start_requested
Server -> glassworks.started (everyone)          season 1, sand 12
Player -> glassmaking.requested {furnace_id: 1}
Server -> glassmaking.started                     sand 9, worker busy
+5 s   -> glassmaking.heated
Player -> glassmaking.bench_requested {furnace_id: 1}
Server -> glassmaking.bench_started               bench 1
+3 s   -> glassmaking.completed                   cooling_ends_at = +8 s
+8 s
Player -> glass.take_requested {bench_id: 1}
Server -> glass.stored                            glass 1
```

### Crack (T5)

Same as T4, but take immediately after completion: `crack_chance` is 100 and the
piece cracks; glass stays 0.

### Sand tick (T2)

At sand 20: +10 s `gained: 6` (26), +20 s `gained: 4` (30), +30 s
`gained: 0` (30).

### Purchase (T6)

Season 1, one furnace, glass 3: purchase costs 3, leaving glass 0. A second
purchase rejects with `not enough glass`. The same formula applies to benches.

### Master disconnect (T7)

Master disconnects while open: server broadcasts `glassworks.closed` with causa
`master_disconnected`, removes pieces, frees workers, and releases the slot.

## Ordering Guarantees

The transport serializes validation, mutation, and emission under one
`asyncio.Lock`. Clients observe facts in the order the server produced them, and
each fact's `state` is the snapshot immediately after its mutation. Concurrent
requests cannot interleave between validation and mutation (T3).

## Contract Changes

Adding, renaming, or removing an event or reason requires updating both
`docs/spec.md` and `specs/001-glassworks/spec.md`, this file, the state schema if
affected, and the scenario coverage matrix before implementation.
