# Quickstart Validation: Cooperative Real-Time Glassworks

**Feature**: `001-glassworks` | **Date**: 2026-11-01

This guide proves the feature end-to-end. Contracts live in
`contracts/events.md` and `contracts/state.schema.json`; rules live in
`data-model.md` and `docs/spec.md`. Commands assume the repository root.

## Prerequisites

- Python 3.11 or newer (`python3 --version`)
- A modern browser with WebSocket support
- Network access to the Vue 3, Phaser 3, and Socket.IO CDNs
- No Node.js, npm, database, or external service

## Install

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
```

`requirements.txt` contains `python-socketio>=5.16` and `uvicorn>=0.51` only.

## Automated Tests

```bash
python -m unittest discover -s tests -v
```

Expected: all tests pass with no real sleeps. Timer tests advance
`ManualClock`; crack tests use a seeded RNG.

Coverage to confirm in the output:

| Scenario | What it proves |
|----------|----------------|
| `test_engine_*` | Rules, validation order, T1-T7 semantics |
| `test_contract` | Every event name, payload, direction, and unicast/broadcast target |
| `test_flows` | T1-T7 over a real Socket.IO connection |
| `test_rules` | Single source of constants and formulas |

## Run

```bash
uvicorn glassworks.server:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000> in two browser tabs.

## Manual Validation

Keep both tabs visible. The HUD MUST show the server snapshot after every fact;
the client MUST NOT update sand, glass, or piece state on its own.

1. **Join and sync (S7)**: tab A chooses Master, tab B chooses Player. Both
   receive `state.synced` with `season: 0`, `season_open: false`, `sand: 12`,
   `glass: 0`, one furnace, one bench, eight free workers.
2. **Open season (S1)**: A clicks Open. Both receive `glassworks.started` with
   `season: 1`, `sand: 12`, `glass: 0`. B's controls become active.
3. **Produce glass (T4)**: B requests a piece on furnace 1. Sand drops to 9 and
   one worker is busy. After about 5 s the furnace is ready. B moves it to bench
   1. After about 3 s cooling starts and the worker is free. After 8 s, B takes
   the glass: glass becomes 1 and the bench is free.
4. **Crack (T5)**: Repeat production and take immediately after cooling starts.
   The piece cracks; glass is unchanged; `crack_chance` is 100.
5. **Sand tick (T2)**: With sand at 20 or less, wait 10 s. Sand rises by 6
   (capped at 30); the next tick gains 4, then 0 at the cap. `sand.stored` is
   emitted every 10 s while open, including `gained: 0`.
6. **Purchase (T6)**: With glass 3 and season 1, B buys a furnace for 3. Glass
   becomes 0 and furnace 2 appears. A second purchase rejects with
   `not enough glass`. Repeat the formula for a bench.
7. **Race (T3)**: With one free furnace, have two players request it at nearly
   the same time. Exactly one receives `glassmaking.started`; the other receives
   `operation.rejected` with `furnace busy`. A single state snapshot results.
8. **Role enforcement**: B (Player) tries to open or close a season and receives
   `only master can open season` / `only master can close season`. A (Master)
   tries to produce or purchase and receives `only players can interact`.
9. **Second Master**: A third tab choosing Master is rejected with
   `a master already exists` and disconnected.
10. **Close season (S2)**: A closes. Both receive `glassworks.closed`; pieces
    disappear, workers free, sand and stored glass persist.
11. **Master disconnect (T7)**: With a season open, close tab A. B receives
    `glassworks.closed` with causa `master_disconnected`. A new tab can choose
    Master and open the next season, which increments `season`.

## Expected Contract Behavior

- Every server fact carries a complete `state`; `operation.rejected` and
  `state.synced` are unicast and never mutate state.
- `state.server_time` and `cooling_ends_at` let the browser render a countdown
  despite clock skew.
- Rejections never leave the client waiting: every request produces exactly one
  success fact or one rejection.
- A malformed or unknown id produces `malformed payload`, `unknown furnace`, or
  `unknown bench`, never an unhandled server error.

## Troubleshooting

| Symptom | Check |
|---------|-------|
| CDN assets fail to load | Network access to the Vue, Phaser, and Socket.IO CDNs |
| Connection rejected as Master | Another Master tab is still connected; disconnect it |
| No events after joining | Confirm the auth payload includes `role` |
| Sand never rises | The season must be open; the tick starts 10 s after start |
| Tests hang | A test is using real sleep instead of `ManualClock` |
| Static file 404 | The requested path must resolve inside `web/` |
