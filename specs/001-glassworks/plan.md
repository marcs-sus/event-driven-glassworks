# Implementation Plan: Cooperative Real-Time Glassworks

**Branch**: `001-glassworks` | **Date**: 2026-11-01 | **Spec**: `specs/001-glassworks/spec.md`

**Input**: Feature specification from `specs/001-glassworks/spec.md`, mirrored at
`docs/spec.md`. Both copies MUST remain identical.

## Summary

Build a single-process, real-time multiplayer glassworks game. A Python 3
Socket.IO server owns all shared state, validates every request, advances timers
from an injectable clock, and broadcasts complete state snapshots with every
fact. The client is a static Vue 3 + Phaser 3 page loaded from a CDN; it emits
requests and renders only server facts. The design separates transport from a
synchronous domain engine so that all rules, races, timers, and probability can
be tested deterministically without sockets or real sleeps.

Four specification gaps MUST be reconciled before implementation (see Phase 0,
R2, R3, R9, and the Scenario Coverage Matrix): two missing season-request
events, a season-numbering contradiction, missing validation rejection reasons,
and missing per-event test scenarios.

## Technical Context

**Language/Version**: Python 3.11+ (verified on the project's Python 3.14.8
interpreter)

**Primary Dependencies**: `python-socketio>=5.16`, `uvicorn>=0.51`; browser
clients use Vue 3, Phaser 3, and the Socket.IO JavaScript client via CDN. No
npm, bundler, or build step.

**Storage**: In-memory process state only; no database and no persistence.

**Testing**: Python standard library `unittest` with
`unittest.IsolatedAsyncioTestCase`; `socketio.AsyncClient` for the transport
integration suite. No additional test dependency. Automated tests are optional
given the schedule.

**Target Platform**: Linux ASGI server; modern desktop and mobile browsers with
WebSocket support.

**Project Type**: Single-process real-time web application (authoritative
server plus static CDN client).

**Performance Goals**: 50 ms scheduler tick; request-to-broadcast p95 under
200 ms on a LAN; state payload bounded by 4 furnaces, 4 benches, and 8 busy
workers; 60 fps client rendering.

**Constraints**: One shared room per process; no persistence; no client build
step; closed runtime dependency list; all durations driven by one injectable
clock; broadcasts carry the complete state.

**Scale/Scope**: One room per server process, all connected clients receive all
facts. State size is O(furnaces + benches + in-progress pieces); a restart
resets the game.

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

| Principle                                    | Gate                                                              | Status                 | Evidence                                                                                                                                               |
| -------------------------------------------- | ----------------------------------------------------------------- | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| I. Server-Authoritative Event Flow           | Client only requests; server validates, mutates, broadcasts       | PASS                   | `transport.py` delegates to a synchronous `engine.py`; clients never receive write authority                                                           |
| II. Single Source of Game Rules              | No duplicated rule literals                                       | PASS                   | All constants and formulas live in `rules.py`; handlers and UI import them only for display                                                            |
| III. Event Contract Discipline               | Documented events, naming, payload validation, per-event scenario | PASS WITH PREREQUISITE | `events.py` is the single name registry; contract in `contracts/events.md`; spec reconciliation (P1) adds two request events and scenarios before code |
| IV. Test-First, Time-Controlled Verification | Failing tests first; deterministic time and randomness            | PASS                   | `ManualClock` and seeded RNG; T1-T7 plus one scenario per event; no real sleeps                                                                        |
| V. Minimal In-Memory Architecture            | Single process, closed stack, domain isolated from transport      | PASS                   | No new runtime dependency; stdlib static-file ASGI wrapper; domain never imports `socketio`                                                            |
| Governance: staged commits                   | One commit per implementation stage                               | PASS                   | Stage plan below defines seven independently reviewable stages, one per tasks phase                                                                    |

No constitutional violations require justification.

**Post-Design Re-evaluation (Phase 1)**: All gates remain PASS. The contract and
data model keep `socketio` out of the domain, define every payload and rejection
reason, and preserve deterministic time and randomness. Prerequisite P1 is the
only outstanding item and is scheduled as the first commit.

## Project Structure

### Documentation (this feature)

```text
specs/001-glassworks/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── events.md
│   └── state.schema.json
└── tasks.md              # created by /speckit.tasks, not by this command
```

### Source Code (repository root)

```text
server.py                 # the whole server, one file, in clearly commented sections:
                          #   1. clock      Clock protocol, SystemClock, ManualClock
                          #   2. events     event names, causa values, rejection reasons
                          #   3. rules      every game constant and formula
                          #   4. models     dataclasses and enums: GameState, Piece, Furnace, Bench
                          #   5. engine     synchronous, transport-free state machine
                          #   6. transport  Socket.IO handlers, auth, broadcast, tick loop
                          #   7. static     stdlib ASGI static-file wrapper (serves client/ at /assets)
                          #   8. entry      ASGI app factory; run with `uvicorn server:app`

client/
├── index.html
├── css/app.css
└── js/
    ├── main.js           # Vue shell, login screen, HUD
    ├── store.js          # server-state mirror and request helpers
    ├── socket.js         # Socket.IO client singleton
    └── scene.js          # Phaser scene: furnaces, benches, pieces

tests/
├── support/
│   ├── manual_clock.py
│   ├── fakes.py          # recording broadcaster and seeded RNG
│   └── transport.py      # in-process uvicorn + Socket.IO client harness
├── unit/
│   ├── test_clock.py
│   ├── test_events.py
│   ├── test_models.py
│   ├── test_rules.py
│   ├── test_engine_seasons.py
│   ├── test_engine_glassmaking.py
│   ├── test_engine_sand.py
│   └── test_engine_purchases.py
└── integration/
    ├── test_contract_us1.py
    ├── test_contract_us2.py
    ├── test_contract_us3.py
    ├── test_contract_us4.py
    ├── test_flows_us1.py
    ├── test_flows_us3.py
    └── test_flows_us4.py

docs/spec.md              # authoritative behavior specification
specs/001-glassworks/spec.md  # feature copy, kept identical
requirements.txt
```

**Structure Decision**: A single project rooted at the repository. The server is
a single `server.py` at the repository root, organized into clearly commented
sections (clock, events, rules, models, engine, transport, static, entry) with no
`glassworks/` package and no packaging step; the client is plain static files in
`client/`, served at `/assets` by the same ASGI process through a small stdlib
wrapper. This avoids `src/` layout indirection, a second process, a bundler, and
any framework beyond the constitution's closed stack. Tests mirror the domain
and transport sections.

**Required Deliverables**: The event panel, the Phaser canvas, and `/assets`
static serving are required deliverables for the professor's rubric; they are
not optional even if the schedule forces cuts elsewhere.

## Implementation Stages

Each stage is exactly one commit, in order, and matches one tasks phase. A stage
is reviewable on its own and includes its own tests.

1. **Specification reconciliation and scaffold** (`docs:`): P1 spec updates,
   mirrored copies, `server.py` scaffold and `client/` directory, CDN page shell.
2. **Foundational domain and transport** (`feat:`): clock, rules, events,
   models, engine skeleton, auth and `state.synced`, static server, test
   harness, Vue/Phaser shell.
3. **Playable season loop** (`feat:`, US1): Master open/close, piece lifecycle,
   take/crack, handlers, and production UI; T1, T3, T4, T5.
4. **Sand regeneration** (`feat:`, US2): tick advancement, broadcast, HUD; T2.
5. **Equipment purchases** (`feat:`, US3): furnace and bench purchase rules,
   handlers, UI; T6.
6. **Session and role safety** (`feat:`, US4): invalid role, duplicate Master,
   role enforcement, payload validation, disconnect close; T7.
7. **Polish and validation** (`docs:`): full suite, quickstart walkthrough,
   contract consistency, performance check, constitution review.

## Complexity Tracking

No violations. The custom static-file wrapper is the simplest way to keep one
process and the closed dependency stack; adding Starlette or a second static
server would violate Principle V.
