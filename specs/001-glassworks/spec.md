# Project Specification

## Overview

Cooperative real-time glassworks. Multiple players share a global sand
stock, a pool of glassblowers, and a glass storage. The Master opens and
closes seasons; players produce glass through furnaces and benches.

## Roles

- **Master**: opens/closes seasons. Does not interact with furnaces,
  benches or purchases. Exactly one Master at a time; the slot is
  released on disconnect, but players have no in-game control to become
  Master — they must reconnect and pick "Master" on the login screen.
- **Player**: interacts with furnaces, benches and purchases.

## Global state

| Field                | Initial | Reset on new season | Notes                                                       |
| :------------------- | :------ | :------------------ | :---------------------------------------------------------- |
| `season`             | 1       | no (increments)     | +1 on each `glassworks.started`; never resets               |
| `sand`               | 12      | yes (12)            | cap 30                                                      |
| `glass`              | 0       | yes (0)             | currency and score                                          |
| `glassblowers_total` | 8       | no                  | fixed                                                       |
| `glassblowers_busy`  | 0       | yes (0)             | pieces in `furnace_heating`/`furnace_ready`/`bench_working` |
| `furnaces`           | 1       | no (persist)        | max 4                                                       |
| `benches`            | 1       | no (persist)        | max 4                                                       |

## Piece lifecycle

1. `furnace_heating` — in furnace, 5 s, 1 worker busy.
2. `furnace_ready` — timer done, clickable, worker still busy.
3. `bench_working` — in bench, 3 s, 1 worker busy.
4. `bench_cooling` — formed, 8 s cooling, worker freed, clickable.
5. `stored` — take succeeded, `glass +1`.
6. `cracked` — take failed, piece removed, `glass` unchanged.

Crack chance during take: `max(0, 1 − elapsed_cooling / 8) * 100%`.

## Events

| Event                         | Emits  | Receives  | Payload                                 | What happens                                      |
| :---------------------------- | :----- | :-------- | :-------------------------------------- | :------------------------------------------------ |
| `glassworks.started`          | Server | Everyone  | state, causa                            | season+1, sand=12, glass=0, pieces cleared        |
| `glassworks.closed`           | Server | Everyone  | state, causa                            | in-progress pieces removed, workers freed         |
| `glassmaking.requested`       | Player | Server    | furnace_id                              | request to start a new piece                      |
| `glassmaking.started`         | Server | Everyone  | state, causa, furnace_id                | sand−3, worker+1, furnace timer 5 s               |
| `glassmaking.heated`          | Server | Everyone  | state, causa, furnace_id                | furnace timer done, piece ready                   |
| `glassmaking.bench_requested` | Player | Server    | furnace_id                              | request to move ready piece to a free bench       |
| `glassmaking.bench_started`   | Server | Everyone  | state, causa, furnace_id, bench_id      | piece moved, bench timer 3 s                      |
| `glassmaking.completed`       | Server | Everyone  | state, causa, bench_id, cooling_ends_at | bench timer done, cooling 8 s, worker freed       |
| `glass.take_requested`        | Player | Server    | bench_id                                | request to take a cooling piece                   |
| `glass.stored`                | Server | Everyone  | state, causa, bench_id                  | take succeeded, glass+1                           |
| `glass.cracked`               | Server | Everyone  | state, causa, bench_id, crack_chance    | take failed, piece removed                        |
| `sand.stored`                 | Server | Everyone  | state, causa, gained                    | sand +min(6, 30−sand) every 10 s; gained=0 at cap |
| `operation.rejected`          | Server | Requester | causa, reason                           | validation failed                                 |
| `furnace.purchase_requested`  | Player | Server    | —                                       | request to buy a furnace                          |
| `furnace.purchased`           | Server | Everyone  | state, causa, furnace_id, cost          | glass−cost, new furnace added                     |
| `bench.purchase_requested`    | Player | Server    | —                                       | request to buy a bench                            |
| `bench.purchased`             | Server | Everyone  | state, causa, bench_id, cost            | glass−cost, new bench added                       |

## Purchase cost

`cost = count * season * 2 + 1`, where `count` is the current number of
furnaces (or benches), including the initial free one.
Examples (season 1, furnaces): 2nd = 3, 3rd = 5, 4th = 7.

## Rejection reasons

- `season not open`
- `not enough sand`
- `not enough glass`
- `no free worker`
- `furnace busy`
- `bench busy`
- `piece not ready`
- `max furnaces reached`
- `max benches reached`
- `only master can open season`
- `only master can close season`
- `a master already exists`
- `only players can interact`
- `no piece to take`

## Rules

1. Game starts with 1 furnace, 1 bench, 12 sand, 0 glass, 8 glassblowers.
2. Season number starts at 1 and increments on each `glassworks.started`.
3. Sand increases by `min(6, 30 − sand)` every 10 s while the season is open.
4. A piece requires 3 sand, 1 free worker and a free furnace.
5. Furnace timer 5 s; bench timer 3 s; cooling 8 s.
6. A worker is busy from `glassmaking.started` until `glassmaking.completed`.
7. On `glassworks.closed`: in-progress pieces are removed, sand is not
   refunded, workers are freed. Stored glass persists.
8. On `glassworks.started`: sand and glass reset; furnaces, benches and
   the season counter persist.
9. If the Master disconnects while a season is open, the server emits
   `glassworks.closed` (causa `master_disconnected`) and releases the
   Master slot. Any player who wants to become Master must reconnect and
   choose "Master" on the login screen.

## Test cases

### T1 — Rejection: not enough sand

Season open, sand=2. Player A emits `glassmaking.requested`. Server
emits `operation.rejected` (reason `not enough sand`) for A only.

### T2 — Time tick with cap

Season open, sand=20. After 10 s → `sand.stored` gained=6 (sand=26);
after 20 s → gained=4 (sand=30); after 30 s → gained=0 (sand stays 30).

### T3 — Race condition: furnace busy

Season open, 1 furnace, 1 bench, 0 pieces in progress. A and B
simultaneously emit `glassmaking.requested` on the same furnace. Server
emits `glassmaking.started` for one and `operation.rejected`
(reason `furnace busy`) for the other.

### T4 — Full flow: stored

Season open, sand=12, 1 free furnace, 1 free bench. A emits
`glassmaking.requested` → `glassmaking.started`. After 5 s →
`glassmaking.heated`. A clicks the furnace again →
`glassmaking.bench_started`. After 3 s → `glassmaking.completed`. A
waits 8 s and clicks the bench → `glass.take_requested` →
`glass.stored` (0% crack). Glass becomes 1.

### T5 — Full flow: cracked

Same setup as T4. After `glassmaking.completed`, A clicks the bench
immediately → `glass.take_requested` → `glass.cracked` (100% crack).
Glass stays 0.

### T6 — Purchase

Season open, 1 furnace, 1 bench, glass=3, season=1. A emits
`furnace.purchase_requested` → `furnace.purchased` (cost=3, glass=0). A
second request is rejected with `not enough glass`.

### T7 — Master disconnect

Season open. Master disconnects. Server emits `glassworks.closed`
(causa `master_disconnected`) for everyone; in-progress pieces are
removed; a new user can log in as Master and start a new season.
