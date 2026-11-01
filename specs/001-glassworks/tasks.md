---
description: "Task list for Cooperative Real-Time Glassworks"
---

# Tasks: Cooperative Real-Time Glassworks

**Input**: Design documents from `specs/001-glassworks/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`,
`contracts/events.md`, `contracts/state.schema.json`, `quickstart.md`

**Tests**: REQUIRED. The constitution mandates test-first development, T1-T7
automation, one scenario per event, injected time, and seeded randomness. Write
each test task first and confirm it fails before starting its implementation.

**Organization**: `spec.md` defines roles, rules, and test cases but no
prioritized user stories. The four stories below are derived from the spec and
the contracts; priorities reflect delivery order and the playable MVP.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on incomplete work)
- **[Story]**: `[US1]`, `[US2]`, `[US3]`, or `[US4]`; setup, foundational, and
  polish tasks have no story label
- Every task names the exact file(s) it changes

## Path Conventions

Single project at the repository root: server package `glassworks/`, static
client `web/`, tests `tests/`, authoritative docs `docs/` and
`specs/001-glassworks/`. No `src/` or `backend/frontend` split.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Reconcile the specification and create the project skeleton.

- [ ] T001 Update `docs/spec.md` with P1.1-P1.5: add `glassworks.start_requested`, `glassworks.close_requested`, `state.synced`, rejection reasons `invalid role`, `unknown furnace`, `unknown bench`, `malformed payload`, `season already open`, correct season numbering (internal 0, first start 1), and the scenario coverage from `research.md`
- [ ] T002 Copy `docs/spec.md` to `specs/001-glassworks/spec.md` and verify both files are byte-identical
- [ ] T003 Create the scaffold: `glassworks/__init__.py`, `tests/__init__.py`, `tests/unit/__init__.py`, `tests/integration/__init__.py`, `tests/support/__init__.py`, `web/css/`, and `web/js/`
- [ ] T004 Create `web/index.html` with CDN script tags for Vue 3, Phaser 3, and the Socket.IO client, plus Vue and Phaser mount elements
- [ ] T005 Create `web/css/app.css` with the two-column layout: game canvas, login overlay, HUD, and controls

**Checkpoint**: Both spec copies carry the reconciled contract; the repository
has empty server, test, and client shells.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared clock, rules, events, models, engine skeleton, transport
bootstrap, and client shell. No story work starts until this phase is complete.

**⚠️ CRITICAL**: Complete every task in this phase before Phase 3.

### Domain primitives

- [ ] T006 [P] Write failing clock tests in `tests/unit/test_clock.py` covering `SystemClock.now()` and `ManualClock` start/advance
- [ ] T007 [P] Implement `glassworks/clock.py` with a `Clock` protocol, `SystemClock`, and `ManualClock` returning epoch seconds
- [ ] T008 [P] Write failing rules tests in `tests/unit/test_rules.py` for sand 12/cap 30, 3 sand per piece, refill `min(6, 30 - sand)` every 10 s, 8 workers, 5/3/8 s durations, 4/4 caps, `count * season * 2 + 1` cost, and the crack formula
- [ ] T009 [P] Implement `glassworks/rules.py` as the only source of constants and pure formulas; no other module may declare these literals
- [ ] T010 [P] Write failing event-registry tests in `tests/unit/test_events.py` that assert every request name ends in `requested`, every server fact uses a past-tense action, and all `causa` and rejection values from `contracts/events.md` exist
- [ ] T011 [P] Implement `glassworks/events.py` with event-name constants, `Causa` values, and rejection reasons from `contracts/events.md`
- [ ] T012 [P] Write failing model tests in `tests/unit/test_models.py` for `Role`, `PieceState`, `Furnace`, `Bench`, `Piece`, and `GameState` defaults/invariants: sand 0..30, glass >= 0, busy 0..8, 1..4 furnaces and benches, at most one piece per container
- [ ] T013 [P] Implement `glassworks/models.py` with dataclasses, enums, and a `snapshot()` serializer conforming to `contracts/state.schema.json`, including `server_time`, `glassblowers`, and epoch deadlines
- [ ] T014 [P] Implement `tests/support/manual_clock.py` and `tests/support/fakes.py` with a recording broadcaster and seeded `random.Random`
- [ ] T015 Implement `glassworks/engine.py` skeleton: construct initial state, session registry with at most one Master, `join`/`leave` from a role, `snapshot()`, and helpers for worker counts and id allocation; depends on T007, T009, T011, T013

### Transport, server, and client shell

- [ ] T016 Implement `glassworks/transport.py` bootstrap: `socketio.AsyncServer`, auth role parsing, `state.synced` unicast, broadcast helper, an `asyncio.Lock` for serialized mutation/emission, and a 50 ms tick task that calls `engine.advance`; depends on T015
- [ ] T017 [P] Implement `glassworks/static.py` with a stdlib ASGI wrapper that delegates `/socket.io` paths and safely serves files under `web/` with a MIME map and `index.html` fallback
- [ ] T018 Implement `glassworks/server.py` composing `static.py` and `socketio.ASGIApp`, exposing `app` for `uvicorn glassworks.server:app`; depends on T016 and T017
- [ ] T019 Implement `tests/support/transport.py` with an in-process `uvicorn.Server` bound to a port-0 loopback socket via `Config.bind_socket` plus an async `socketio.AsyncClient` fixture
- [ ] T020 Write `tests/integration/test_transport_boot.py` proving a client connects with each role, receives `state.synced` with the schema fields, and the server starts/stops without leaked tasks; depends on T018 and T019
- [ ] T021 [P] Implement `web/js/socket.js` with the Socket.IO client, `{role}` auth, connect/reconnect handling, and event dispatch
- [ ] T022 [P] Implement `web/js/store.js` with the latest snapshot, server-time offset, and request emitters for every client event
- [ ] T023 Implement `web/js/scene.js` Phaser scene skeleton that draws furnaces and benches from a snapshot; depends on T022
- [ ] T024 Implement `web/js/main.js` Vue shell: login overlay, role selection, HUD skeleton, and event-to-store wiring; depends on T021 and T022

**Checkpoint**: Tests for clock, rules, events, models, and transport boot pass;
a browser client can connect, choose a role, and render an empty lobby.

---

## Phase 3: User Story 1 - Playable Season Loop (Priority: P1) 🎯 MVP

**Goal**: A Master opens and closes a season while Players produce glass through
furnaces and benches, with stored and cracked outcomes, worker accounting, and
race-safe validation.

**Independent Test**: With a manual clock, Master opens season 1 (sand 12, glass
0); Player produces a piece, moves it, completes cooling, and takes it after 8 s
to store glass; repeat and take immediately to crack; a second simultaneous
request on one furnace yields one success and one `furnace busy`; Master closes
and pieces disappear while glass persists. Covers T1, T3, T4, T5.

### Tests for User Story 1 ⚠️

> Write these tests first and confirm they fail.

- [ ] T025 [P] [US1] Write season-engine tests in `tests/unit/test_engine_seasons.py`: first start yields season 1, sand 12, glass 0, pieces cleared; close frees workers, removes pieces, preserves sand/glass; reopen increments season
- [ ] T026 [P] [US1] Write production tests in `tests/unit/test_engine_glassmaking.py` for T4 and T5: sand -3, worker busy 5 s + 3 s, `furnace_ready`, bench selection, cooling ends at +8 s, 0% crack after 8 s, 100% crack immediately
- [ ] T027 [P] [US1] Write rejection and race tests in `tests/unit/test_engine_rejections.py` for T1 (`not enough sand`), T3 (`furnace busy`), `no free worker`, `piece not ready`, `bench busy`, `no piece to take`, and closed-season actions
- [ ] T028 [P] [US1] Write event-contract tests in `tests/integration/test_contract_us1.py` for `glassworks.start_requested`, `glassworks.started`, `glassworks.close_requested`, `glassworks.closed`, `glassmaking.requested`, `glassmaking.started`, `glassmaking.heated`, `glassmaking.bench_requested`, `glassmaking.bench_started`, `glassmaking.completed`, `glass.take_requested`, `glass.stored`, `glass.cracked`, and `operation.rejected` payloads and broadcast targets
- [ ] T029 [P] [US1] Write the T4/T5 socket flow in `tests/integration/test_flows_us1.py` using the transport harness and `ManualClock`

### Implementation for User Story 1

- [ ] T030 [US1] Implement season start and close in `glassworks/engine.py`: season +1, sand 12, glass 0, clear pieces, free workers, schedule sand tick, close with `master` or `master_disconnected` causa
- [ ] T031 [US1] Implement piece request and heating in `glassworks/engine.py`: validate 3 sand, free worker, free furnace; create `furnace_heating` with `ready_at = now + 5`; emit `glassmaking.started`
- [ ] T032 [US1] Implement bench movement, completion, take, and crack in `glassworks/engine.py`: lowest free bench, `bench_working` 3 s, free worker at completion, `cooling_started_at`/`cooling_ends_at`, injected RNG crack roll, stored/cracked removal
- [ ] T033 [US1] Register season and production handlers in `glassworks/transport.py`, validating request shape and emitting every fact from `contracts/events.md` under the serialization lock
- [ ] T034 [US1] Add season and production request helpers plus HUD selectors to `web/js/store.js`
- [ ] T035 [US1] Add clickable furnace/bench interactions and ready/cooling visuals to `web/js/scene.js`
- [ ] T036 [US1] Add Master open/close controls, piece status, worker counts, and player action buttons to `web/js/main.js`

**Checkpoint**: US1 is fully playable in two browser tabs and all T1/T3/T4/T5
tests pass independently.

---

## Phase 4: User Story 2 - Sand Regeneration (Priority: P2)

**Goal**: While a season is open, sand rises by `min(6, 30 - sand)` every 10 s,
including a `gained: 0` fact at the cap.

**Independent Test**: Advance `ManualClock` by 10 s from sand 20: `sand.stored`
gained 6 (26); by 20 s: gained 4 (30); by 30 s: gained 0 (30). Covers T2.

### Tests for User Story 2 ⚠️

- [ ] T037 [P] [US2] Write T2 sand-tick tests in `tests/unit/test_engine_sand.py`, including multiple missed ticks in one `advance`, cap behavior, and no ticks while closed
- [ ] T038 [P] [US2] Write `sand.stored` contract tests in `tests/integration/test_contract_us2.py` for payload, cause `sand_tick`, and broadcast target

### Implementation for User Story 2

- [ ] T039 [US2] Implement sand advancement in `glassworks/engine.py`: process due ticks in deadline order, apply `gained = min(6, 30 - sand)`, reschedule +10 s, emit at cap, and stop while closed
- [ ] T040 [US2] Wire the transport tick task in `glassworks/transport.py` to call `engine.advance(clock.now())` under the lock and broadcast returned facts
- [ ] T041 [US2] Add sand, cap, worker, and next-tick display to the HUD in `web/js/main.js`

**Checkpoint**: T2 passes at engine and socket level; the HUD reflects each tick.

---

## Phase 5: User Story 3 - Equipment Purchases (Priority: P3)

**Goal**: Players spend glass to add furnaces and benches up to 4 each, using
`count * season * 2 + 1` for the current count before purchase.

**Independent Test**: Season 1, one furnace, glass 3: purchase costs 3 and adds
furnace 2; a second purchase rejects `not enough glass`; at 4 furnaces the next
rejects `max furnaces reached`; the same checks pass for benches. Covers T6.

### Tests for User Story 3 ⚠️

- [ ] T042 [P] [US3] Write T6 and bench-purchase tests in `tests/unit/test_engine_purchases.py`, including cost at seasons 1 and 2, caps, and insufficient glass
- [ ] T043 [P] [US3] Write purchase contract tests in `tests/integration/test_contract_us3.py` for `furnace.purchase_requested`, `furnace.purchased`, `bench.purchase_requested`, and `bench.purchased`
- [ ] T044 [P] [US3] Write the T6 socket flow in `tests/integration/test_flows_us3.py`

### Implementation for User Story 3

- [ ] T045 [US3] Implement furnace and bench purchases in `glassworks/engine.py`: cost from `rules.py`, glass check, max 4, next id, glass deduction, fact emission
- [ ] T046 [US3] Register purchase handlers in `glassworks/transport.py` and reject the Master with `only players can interact`
- [ ] T047 [US3] Add purchase request helpers and affordability selectors to `web/js/store.js`
- [ ] T048 [US3] Add furnace/bench purchase buttons with live costs and disabled states to `web/js/main.js`

**Checkpoint**: T6 passes for both equipment types; the client can buy and render
new furnaces and benches.

---

## Phase 6: User Story 4 - Session and Role Safety (Priority: P4)

**Goal**: Invalid roles, duplicate Masters, unauthorized actions, malformed
payloads, and Master disconnects cannot corrupt state or leave clients without a
seat.

**Independent Test**: Connect with a bad role and receive `invalid role` then a
disconnect; a second Master receives `a master already exists`; Player open and
Master production attempts reject with the documented reasons; malformed and
unknown ids reject without exceptions; a Master disconnect while open broadcasts
`glassworks.closed` with causa `master_disconnected` and frees the slot (T7).

### Tests for User Story 4 ⚠️

- [ ] T049 [P] [US4] Write session-safety contract tests in `tests/integration/test_contract_us4.py` for invalid role, duplicate Master, role enforcement, every new rejection reason, and `state.synced` on join/reconnect
- [ ] T050 [P] [US4] Write the T7 and rejection socket flows in `tests/integration/test_flows_us4.py`

### Implementation for User Story 4

- [ ] T051 [US4] Implement auth validation and duplicate-Master rejection in `glassworks/transport.py`, emitting `operation.rejected` with causa `connection` before disconnect
- [ ] T052 [US4] Add payload-shape and id-validation helpers in `glassworks/engine.py` for `malformed payload`, `unknown furnace`, and `unknown bench`
- [ ] T053 [US4] Enforce role and validation order across every handler in `glassworks/transport.py`, matching the table in `data-model.md`
- [ ] T054 [US4] Implement Master disconnect handling in `glassworks/transport.py`: close an open season with causa `master_disconnected`, free workers, release the slot, and keep stored glass
- [ ] T055 [US4] Add login errors, disconnect notices, and role-specific control visibility to `web/js/socket.js`, `web/js/store.js`, and `web/js/main.js`

**Checkpoint**: T7 and every rejection reason pass; no malformed request can raise
an unhandled server error.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Validate the whole system against the constitution and quickstart.

- [ ] T056 Run `python -m unittest discover -s tests -v` from the repository root, fix failures, and record the result in `specs/001-glassworks/quickstart.md`
- [ ] T057 Execute every manual scenario in `specs/001-glassworks/quickstart.md` with two browsers and record deviations in the same file
- [ ] T058 Verify `docs/spec.md` and `specs/001-glassworks/spec.md` remain identical and every event in `specs/001-glassworks/contracts/events.md` has a Test Cases scenario in both copies
- [ ] T059 Validate snapshots against `specs/001-glassworks/contracts/state.schema.json` with a fixture test in `tests/integration/test_contract_us4.py`
- [ ] T060 Review the implementation against `.specify/memory/constitution.md` and fix any drift in `glassworks/`, `web/`, or both spec copies
- [ ] T061 Measure tick cadence and request-to-broadcast latency against the goals in `specs/001-glassworks/plan.md`; record the result in `specs/001-glassworks/quickstart.md`
- [ ] T062 Confirm the git history has exactly one commit per phase and that each commit contains its tests, using `specs/001-glassworks/plan.md` as the stage reference

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 Setup**: no dependencies; must finish first.
- **Phase 2 Foundational**: depends on Phase 1; blocks all stories.
- **Phase 3 US1 (P1)**: depends on Phase 2; delivers the MVP.
- **Phase 4 US2 (P2)**: depends on US1 because the tick runs only in an open
  season and uses the same engine/transport files.
- **Phase 5 US3 (P3)**: depends on US1 for season/glass state and on US2 only for
  file ordering in `engine.py`/`transport.py`; it is behaviorally independent.
- **Phase 6 US4 (P4)**: depends on US1-US3 handlers because it hardens their
  validation and disconnect paths.
- **Phase 7 Polish**: depends on all desired stories.

### Within Each User Story

1. Tests first; confirm they fail.
2. Rules and models already exist from Phase 2; do not duplicate constants.
3. Engine methods before transport handlers.
4. Transport before UI.
5. Run the story's tests at its checkpoint.

### Same-File Sequencing

`glassworks/engine.py`, `glassworks/transport.py`, and `web/js/main.js` are
shared across stories. Tasks touching those files are intentionally not marked
`[P]` and must run in ID order. Tests in different files may run in parallel.

## Parallel Opportunities

- Phase 2: T006, T008, T010, T012, T014 and the implementations T007, T009,
  T011, T013 touch different files and can run in parallel once their tests
  exist.
- Phase 3: T025-T029 are five independent test files and can be written in
  parallel.
- Phase 4: T037 and T038 can run in parallel.
- Phase 5: T042, T043, and T044 can run in parallel.
- Phase 6: T049 and T050 can run in parallel.

### Parallel Example: User Story 1 Tests

```bash
# Write and run these five failing tests together:
python -m unittest tests.unit.test_engine_seasons -v
python -m unittest tests.unit.test_engine_glassmaking -v
python -m unittest tests.unit.test_engine_rejections -v
python -m unittest tests.integration.test_contract_us1 -v
python -m unittest tests.integration.test_flows_us1 -v
```

### Parallel Example: Foundational Primitives

```bash
# Independent modules; tests precede each implementation:
python -m unittest tests.unit.test_clock -v
python -m unittest tests.unit.test_rules -v
python -m unittest tests.unit.test_events -v
python -m unittest tests.unit.test_models -v
```

## Contract Coverage

| Event | Covered by |
|-------|------------|
| `glassworks.start_requested` | T028, T030 |
| `glassworks.started` | T025, T028, T030 |
| `glassworks.close_requested` | T028, T030 |
| `glassworks.closed` | T025, T028, T030, T054 |
| `glassmaking.requested` | T026, T028, T031 |
| `glassmaking.started` | T026, T028, T031 |
| `glassmaking.heated` | T026, T028, T031 |
| `glassmaking.bench_requested` | T026, T028, T032 |
| `glassmaking.bench_started` | T026, T028, T032 |
| `glassmaking.completed` | T026, T028, T032 |
| `glass.take_requested` | T026, T028, T032 |
| `glass.stored` | T026, T028, T032 |
| `glass.cracked` | T026, T028, T032 |
| `sand.stored` | T037, T038, T039 |
| `operation.rejected` | T027, T028, T049, T053 |
| `furnace.purchase_requested` | T043, T045, T046 |
| `furnace.purchased` | T043, T045, T046 |
| `bench.purchase_requested` | T043, T045, T046 |
| `bench.purchased` | T043, T045, T046 |
| `state.synced` | T020, T049 |

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 and Phase 2.
2. Complete Phase 3 (US1).
3. Run T1, T3, T4, and T5 plus the US1 contract tests.
4. Validate two-browser play from `quickstart.md`; this is the demoable MVP.

### Incremental Delivery

1. Phase 1 + Phase 2 → foundation ready.
2. US1 → playable season loop (MVP).
3. US2 → sand economy.
4. US3 → equipment progression.
5. US4 → hardened sessions and role safety.
6. Phase 7 → full quickstart and constitution validation.

Each phase is one commit, satisfying the constitution's staged-commit rule.

## Notes

- [P] means different files and no incomplete dependency; shared-file tasks are
  never parallel.
- Every event in `contracts/events.md` has at least one test task above and one
  spec scenario added in T001.
- All timers use `ManualClock` in tests; no task may introduce `time.sleep` or
  `asyncio.sleep` in the suite.
- The client never computes authoritative state; all UI values derive from the
  latest server snapshot or display-only countdowns.
- Stop at each checkpoint and run that story's tests before proceeding.
