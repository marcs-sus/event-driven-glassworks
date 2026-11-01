# Phase 1 Data Model: Cooperative Real-Time Glassworks

**Feature**: `001-glassworks` | **Date**: 2026-11-01

All state is in memory in one process. Identifiers are integers. Times are epoch
seconds from the injected clock. The authoritative serialized shape is
`contracts/state.schema.json`.

## Enumerations

### Role

| Value | Meaning |
|-------|---------|
| `master` | Opens and closes seasons; cannot interact with production or purchases |
| `player` | Produces glass and buys equipment; cannot open or close seasons |

Exactly zero or one connection may hold `master`. Any number of connections may
hold `player`.

### PieceState

| Value | Location | Worker busy | Clickable | Terminal |
|-------|----------|-------------|-----------|----------|
| `furnace_heating` | Furnace | Yes | No | No |
| `furnace_ready` | Furnace | Yes | Yes (move to bench) | No |
| `bench_working` | Bench | Yes | No | No |
| `bench_cooling` | Bench | No | Yes (take glass) | No |
| `stored` | None | No | No | Yes, removed immediately |
| `cracked` | None | No | No | Yes, removed immediately |

## Entities

### Session

A connected Socket.IO client and its chosen role.

| Field | Type | Rules |
|-------|------|-------|
| `sid` | string | Unique per connection; assigned by Socket.IO |
| `role` | `Role` | Required; from connection auth |
| `name` | string or null | Optional display label; not part of game state |

Sessions are not serialized into `state`. A session exists only while connected.

### GameState

The single shared room.

| Field | Type | Initial | Rules |
|-------|------|---------|-------|
| `season` | integer | 0 | Non-negative; +1 on every successful `glassworks.started` (P1.3) |
| `season_open` | boolean | false | True only between started and closed |
| `sand` | integer | 12 | 0..30; reset to 12 on start |
| `glass` | integer | 0 | >= 0; reset to 0 on start; persists across close |
| `glassblowers_total` | integer | 8 | Fixed constant, never changes |
| `glassblowers_busy` | integer | 0 | Derived; 0..8; reset to 0 on start and close |
| `furnaces` | map[int, Furnace] | `{1: empty}` | 1..4 entries; persists across seasons |
| `benches` | map[int, Bench] | `{1: empty}` | 1..4 entries; persists across seasons |
| `pieces` | map[int, Piece] | empty | Only exists while open; cleared on start and close |
| `master_sid` | string or null | null | Not serialized; at most one |
| `next_piece_id` | integer | 1 | Monotonic; not serialized |
| `next_sand_tick_at` | float or null | null | Not serialized; start + 10 s, then +10 s |
| `next_furnace_id` | integer | 2 | Not serialized; highest + 1 |
| `next_bench_id` | integer | 2 | Not serialized; highest + 1 |

### Furnace

| Field | Type | Rules |
|-------|------|-------|
| `id` | integer | 1..4, stable for the life of the process |
| `piece_id` | integer or null | Null when free; otherwise an existing piece in `furnace_heating` or `furnace_ready` |

A furnace holds at most one piece. A furnace is busy when `piece_id` is not
null.

### Bench

| Field | Type | Rules |
|-------|------|-------|
| `id` | integer | 1..4, stable for the life of the process |
| `piece_id` | integer or null | Null when free; otherwise an existing piece in `bench_working` or `bench_cooling` |
| `cooling_ends_at` | float or null | Set only while the piece is `bench_cooling`; else null |

A bench holds at most one piece. A bench is busy when `piece_id` is not null.
Bench requests always choose the lowest-id free bench (R12).

### Piece

| Field | Type | Rules |
|-------|------|-------|
| `id` | integer | Monotonic process-wide id |
| `state` | `PieceState` | One of the four non-terminal states while present |
| `furnace_id` | integer or null | Set for `furnace_heating` and `furnace_ready` only |
| `bench_id` | integer or null | Set for `bench_working` and `bench_cooling` only |
| `ready_at` | float or null | Deadline for heating or bench work; null during cooling |
| `cooling_started_at` | float or null | Equal to the bench deadline when cooling begins |
| `cooling_ends_at` | float or null | `cooling_started_at + 8`; null outside cooling |

## Relationships

```text
GameState 1 ── * Furnace 0..1 ── Piece
GameState 1 ── * Bench   0..1 ── Piece
GameState 1 ── * Piece
Session   * ── 1 Role; at most one Session has Role.master
```

Every piece present in `pieces` is referenced by exactly one furnace or one
bench, and every occupied furnace or bench references exactly one piece.

## Validation Rules by Request

| Request | Checks in order | Rejection |
|---------|-----------------|-----------|
| Any | Payload is a mapping and required ids are integers | `malformed payload` |
| Any | Caller has a valid role | `invalid role` |
| Any player action | Caller is not the Master | `only players can interact` |
| Any season action | Caller is the Master | `only master can open season` / `only master can close season` |
| Any action except open | `season_open` is true | `season not open` |
| `glassworks.start_requested` | Season is not already open | `season already open` |
| `glassmaking.requested` | Furnace id exists | `unknown furnace` |
| `glassmaking.requested` | Furnace is free | `furnace busy` |
| `glassmaking.requested` | `sand >= 3` | `not enough sand` |
| `glassmaking.requested` | Free worker exists | `no free worker` |
| `glassmaking.bench_requested` | Furnace id exists | `unknown furnace` |
| `glassmaking.bench_requested` | Piece is `furnace_ready` | `piece not ready` |
| `glassmaking.bench_requested` | A bench is free | `bench busy` |
| `glass.take_requested` | Bench id exists | `unknown bench` |
| `glass.take_requested` | Piece is `bench_cooling` | `piece not ready` |
| `glass.take_requested` | Bench has a piece | `no piece to take` |
| `furnace.purchase_requested` | Furnace count < 4 | `max furnaces reached` |
| `furnace.purchase_requested` | `glass >= cost` | `not enough glass` |
| `bench.purchase_requested` | Bench count < 4 | `max benches reached` |
| `bench.purchase_requested` | `glass >= cost` | `not enough glass` |
| Connection | Role is `master` or `player` | `invalid role` (then disconnect) |
| Connection | Master role and slot free | `a master already exists` (then disconnect) |

The order of checks is part of the contract when multiple conditions fail; the
right-hand reason is the one emitted.

## State Transitions

### Room

| From | Trigger | Effects |
|------|---------|---------|
| closed | Master `glassworks.start_requested` | `season += 1`; `season_open = true`; `sand = 12`; `glass = 0`; all pieces removed; all furnaces/benches emptied; busy = 0; `next_sand_tick_at = now + 10`; emit `glassworks.started` |
| open | Master `glassworks.close_requested` | `season_open = false`; all pieces removed; all furnaces/benches emptied; busy = 0; sand and glass unchanged; `next_sand_tick_at = null`; emit `glassworks.closed` causa `master` |
| open | Master disconnect | Same as close with causa `master_disconnected`; then `master_sid = null` |
| closed | Master disconnect | Release `master_sid` only |

### Piece

| From | Trigger | Effects |
|------|---------|---------|
| none | Player `glassmaking.requested` on free furnace | `sand -= 3`; busy +1; create piece `furnace_heating`; `ready_at = now + 5`; furnace occupied; emit `glassmaking.started` |
| `furnace_heating` | Tick at `ready_at` | State becomes `furnace_ready`; worker stays busy; emit `glassmaking.heated` |
| `furnace_ready` | Player `glassmaking.bench_requested` | Furnace freed; lowest free bench occupied; state `bench_working`; `ready_at = now + 3`; emit `glassmaking.bench_started` |
| `bench_working` | Tick at `ready_at` | State `bench_cooling`; busy -1; `cooling_started_at = ready_at`; `cooling_ends_at = ready_at + 8`; `ready_at = null`; emit `glassmaking.completed` |
| `bench_cooling` | Player `glass.take_requested`, stored | `glass += 1`; bench freed; piece removed; emit `glass.stored` |
| `bench_cooling` | Player `glass.take_requested`, cracked | Glass unchanged; bench freed; piece removed; emit `glass.cracked` with `crack_chance` |
| any present | Season start or close | Piece removed; furnace/bench cleared; busy recalculated |

### Economy

| From | Trigger | Effects |
|------|---------|---------|
| open, sand < 30 | Tick at `next_sand_tick_at` | `gained = min(6, 30 - sand)`; `sand += gained`; emit `sand.stored` (including `gained = 0` at cap); schedule +10 s |
| open, any sand | Tick at `next_sand_tick_at` | Same as above; `gained = 0` when capped |
| open | Player `furnace.purchase_requested` | `cost = furnace_count * season * 2 + 1`; `glass -= cost`; add furnace with next id; emit `furnace.purchased` |
| open | Player `bench.purchase_requested` | `cost = bench_count * season * 2 + 1`; `glass -= cost`; add bench with next id; emit `bench.purchased` |

## Crack Outcome

At take time: `elapsed = max(0, now - cooling_started_at)`,
`chance_percent = max(0, 1 - elapsed / 8) * 100`, and the piece cracks when
`rng.random() * 100 < chance_percent`. At or after 8 s the chance is 0, so a
stored outcome is guaranteed; immediately after completion the chance is 100,
so a cracked outcome is guaranteed (R13).

## Invariants

1. `0 <= sand <= 30`, `glass >= 0`, `season >= 0`.
2. `1 <= len(furnaces) <= 4`, `1 <= len(benches) <= 4`.
3. `glassblowers_busy` equals the count of pieces in `furnace_heating`,
   `furnace_ready`, or `bench_working`, and is at most 8.
4. A furnace or bench holds at most one piece; a piece is held by at most one
   container.
5. `season_open` is false implies `pieces` is empty and busy is 0.
6. After `glassworks.started`, `sand == 12`, `glass == 0`, and `season` is the
   previous value plus 1.
7. `cooling_ends_at == cooling_started_at + 8` whenever cooling is active.
8. At most one session has role `master`.
9. `next_sand_tick_at` is null while closed and strictly 10 s after the last
   processed tick while open.
10. State never leaves the process and is not persisted.

## Serialization

The broadcast `state` is produced from the model on every fact and MUST conform
to `contracts/state.schema.json`. Derived fields (`free`, `glassblowers`,
`server_time`) are computed at serialization time. Internal fields (`master_sid`,
`next_*`, `master` session) are never serialized.
